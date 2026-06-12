"""Business logic for Financial Statement (FS) Report Master operations."""

import logging
import uuid
from psycopg2.extras import execute_values
from common_functions import config, utils

logger = logging.getLogger(__name__)

# Define a static namespace UUID for deterministic node ID generation.
# This ensures that the same node name always yields the exact same UUID.
FS_NAMESPACE = uuid.UUID("3e4499d3-61a7-47b8-b19e-bd9d74cfc737")


def get_node_id(fs_type: str, fs_node_name: str) -> str:
    """Generates a deterministic UUID based on fs_type and node name."""
    if not fs_type or not fs_node_name:
        return None
    unique_key = f"{fs_type}:{fs_node_name.lower().strip()}"
    return str(uuid.uuid5(FS_NAMESPACE, unique_key))


def f_insert_fs_report_master(records: list, connection=None) -> tuple:
    """
    Inserts or upserts records into the fs_report_master table.

    The primary key is fs_node_id.
    If a conflict occurs on fs_node_id, it will update the remaining columns.

    Args:
        records:      List of dictionaries, each containing:
                      - company_id (str, UUID format, Mandatory)
                      - fs_type (str, up to 10 chars, Mandatory, e.g., 'BS', 'PNL', 'CF')
                      - fs_node_name (str, up to 100 chars, Mandatory)
                      - fs_node_id (str, UUID format, Optional/Generated if missing)
                      - parent_fs_node_id (str, UUID format, Optional/Nullable)
                      - parent_node_name (str, Optional, used to resolve parent ID if missing)
                      - node_seq (int, smallint, Mandatory)
                      - reporting_node_flag (bool, Mandatory)
                      - mapped_coa_node_id (str, UUID format, Optional/Nullable)
        connection:   Active database connection. If None, a new connection will be established.

    Returns:
        tuple: (status_code, status_description, error_message, response_body)
    """
    conn = connection
    cursor = None
    own_connection = False

    try:
        # -------------------------------------------------
        # 1. Validate Inputs
        # -------------------------------------------------
        if not isinstance(records, list):
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "records must be a list of dictionaries"
            )

        if not records:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "records list cannot be empty"
            )

        # Validate mandatory fields in each record and pre-process/resolve IDs
        processed_records = []
        mandatory_fields = ["company_id", "fs_type", "fs_node_name", "node_seq", "reporting_node_flag"]
        
        for idx, r in enumerate(records):
            if not isinstance(r, dict):
                raise utils.CustomValidationException(
                    config.STATUS_INVALID_INPUT,
                    config.DESC_MSG0001,
                    f"Record at index {idx} is not a dictionary"
                )
            for field in mandatory_fields:
                if field not in r or r.get(field) is None:
                    raise utils.CustomValidationException(
                        config.STATUS_INVALID_INPUT,
                        config.DESC_MSG0001,
                        f"Missing or null mandatory field '{field}' at index {idx}"
                    )

            # Resolve fs_node_id if missing or empty
            fs_node_id = r.get("fs_node_id")
            if not fs_node_id:
                fs_node_id = get_node_id(r["fs_type"], r["fs_node_name"])

            # Resolve parent_fs_node_id if missing but parent_node_name is provided
            parent_fs_node_id = r.get("parent_fs_node_id")
            if not parent_fs_node_id and r.get("parent_node_name"):
                parent_fs_node_id = get_node_id(r["fs_type"], r["parent_node_name"])

            processed_records.append({
                "fs_node_id": fs_node_id,
                "company_id": r["company_id"],
                "fs_type": r["fs_type"],
                "fs_node_name": r["fs_node_name"],
                "parent_fs_node_id": parent_fs_node_id,
                "node_seq": r["node_seq"],
                "reporting_node_flag": r["reporting_node_flag"],
                "mapped_coa_node_id": r.get("mapped_coa_node_id")
            })

        # -------------------------------------------------
        # 2. Database Connection
        # -------------------------------------------------
        if not conn:
            conn = utils.f_connect_to_db()
            if not conn:
                raise utils.CustomValidationException(
                    config.STATUS_SYSTEM_EXCEPTION,
                    config.DESC_MSG0004,
                    config.ERR_MSG0010
                )
            own_connection = True

        cursor = conn.cursor()

        # -------------------------------------------------
        # 3. Validate company_id exists in company_master
        # -------------------------------------------------
        # We validate utilizing the company_id of the first record as they should belong to the same company run
        sample_company_id = processed_records[0]["company_id"]
        cursor.execute(
            f'SELECT company_id FROM "{config.SCHEMANAME}".company_master WHERE company_id = %s',
            (sample_company_id,)
        )
        if cursor.fetchone() is None:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                config.ERR_MSG0181.format(company_id=sample_company_id)
            )

        # -------------------------------------------------
        # 4. Build & Execute INSERT / UPSERT Query
        # -------------------------------------------------
        query = f"""
            INSERT INTO "{config.SCHEMANAME}".fs_report_master (
                fs_node_id,
                company_id,
                fs_type,
                fs_node_name,
                parent_fs_node_id,
                node_seq,
                reporting_node_flag,
                mapped_coa_node_id
            ) VALUES %s
            ON CONFLICT (fs_node_id)
            DO UPDATE SET
                company_id = EXCLUDED.company_id,
                fs_type = EXCLUDED.fs_type,
                fs_node_name = EXCLUDED.fs_node_name,
                parent_fs_node_id = EXCLUDED.parent_fs_node_id,
                node_seq = EXCLUDED.node_seq,
                reporting_node_flag = EXCLUDED.reporting_node_flag,
                mapped_coa_node_id = EXCLUDED.mapped_coa_node_id;
        """

        values = [
            (
                r['fs_node_id'],
                r['company_id'],
                r['fs_type'],
                r['fs_node_name'],
                r['parent_fs_node_id'],
                r['node_seq'],
                r['reporting_node_flag'],
                r['mapped_coa_node_id']
            )
            for r in processed_records
        ]

        execute_values(cursor, query, values)

        if own_connection:
            conn.commit()

        logger.info(f"Successfully inserted/updated {len(processed_records)} records in fs_report_master.")

        response_body = {
            "message": "Data inserted/updated successfully",
            "count": len(processed_records)
        }

        return (config.STATUS_SUCCESS, config.DESC_MSG0007, None, response_body)

    except utils.CustomValidationException as e:
        if conn and own_connection:
            conn.rollback()
        return e.status_code, e.status_description, e.error_message, None

    except Exception as e:
        logger.error(f"Error inserting fs_report_master: {e}")
        if conn and own_connection:
            conn.rollback()
        return (config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e), None)

    finally:
        try:
            if cursor:
                cursor.close()
            if conn and own_connection:
                conn.close()
        except Exception as close_err:
            logger.error(f"Error closing cursor or connection: {close_err}")
