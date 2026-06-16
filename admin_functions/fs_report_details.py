"""Business logic for Financial Statement (FS) Report Details operations."""

import logging
from psycopg2.extras import execute_values
from common_functions import config, utils

logger = logging.getLogger(__name__)


def f_insert_fs_report_details(records: list, connection=None) -> tuple:
    """
    Inserts or upserts records into the fs_report_details table.

    The composite primary key is (tb_id, fs_node_id).
    On conflict, all non-key columns are updated with the incoming values.

    Args:
        records:    List of dictionaries, each containing:
                    - tb_id             (str, UUID format, Mandatory) — FK → trial_balance.tb_id
                    - fs_type           (str, up to 10 chars, Mandatory, e.g. 'BS', 'PNL', 'CF')
                    - fs_node_id        (str, UUID format, Optional/Nullable)
                    - fs_node_name      (str, Mandatory)
                    - parent_fs_node_id (str, UUID format, Optional/Nullable)
                    - node_seq          (int, smallint, Optional/Nullable)
                    - reporting_node_flag (bool, Mandatory)
                    - balance           (float, numeric(20,2), Optional/Nullable)
        connection: Active database connection. If None, a new one will be established.

    Returns:
        tuple: (status_code, status_description, error_message, response_body)
    """
    conn = connection
    cursor = None
    own_connection = False

    try:
        # -----------------------------------------------------------------
        # 1. Validate Inputs
        # -----------------------------------------------------------------
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

        mandatory_fields = ["tb_id", "fs_type", "fs_node_name", "reporting_node_flag"]

        processed_records = []
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

            processed_records.append({
                "tb_id":               r["tb_id"],
                "fs_node_id":          r.get("fs_node_id") or None,
                "fs_type":             r["fs_type"],
                "fs_node_name":        r["fs_node_name"],
                "parent_fs_node_id":   r.get("parent_fs_node_id"),
                "node_seq":            r.get("node_seq"),
                "reporting_node_flag": r["reporting_node_flag"],
                "balance":             r.get("balance"),
            })

        # -----------------------------------------------------------------
        # 2. Database Connection
        # -----------------------------------------------------------------
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

        # -----------------------------------------------------------------
        # 3. Validate tb_id exists in trial_balance
        # -----------------------------------------------------------------
        sample_tb_id = processed_records[0]["tb_id"]
        cursor.execute(
            f'SELECT tb_id FROM "{config.SCHEMANAME}".trial_balance WHERE tb_id = %s',
            (sample_tb_id,)
        )
        if cursor.fetchone() is None:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                f"tb_id '{sample_tb_id}' does not exist in trial_balance"
            )

        # -----------------------------------------------------------------
        # 4. Build & Execute INSERT / UPSERT Query
        # -----------------------------------------------------------------
        query = f"""
            INSERT INTO "{config.SCHEMANAME}".fs_report_details (
                tb_id,
                fs_type,
                fs_node_id,
                fs_node_name,
                parent_fs_node_id,
                node_seq,
                reporting_node_flag,
                balance
            ) VALUES %s
            ON CONFLICT (tb_id, fs_node_id)
            DO UPDATE SET
                fs_type             = EXCLUDED.fs_type,
                fs_node_name        = EXCLUDED.fs_node_name,
                parent_fs_node_id   = EXCLUDED.parent_fs_node_id,
                node_seq            = EXCLUDED.node_seq,
                reporting_node_flag = EXCLUDED.reporting_node_flag,
                balance             = EXCLUDED.balance;
        """

        values = [
            (
                r["tb_id"],
                r["fs_type"],
                r["fs_node_id"],
                r["fs_node_name"],
                r["parent_fs_node_id"],
                r["node_seq"],
                r["reporting_node_flag"],
                r["balance"],
            )
            for r in processed_records
        ]

        execute_values(cursor, query, values)

        # -----------------------------------------------------------------
        # 5. Define & Execute PL/pgSQL Balance Calculation Function
        # -----------------------------------------------------------------
        create_function_query = f"""
        CREATE OR REPLACE FUNCTION "{config.SCHEMANAME}".calculate_fs_report_details(p_tb_id UUID)
        RETURNS VOID AS $$
        DECLARE
            v_rows_updated INTEGER;
        BEGIN
            -- 1. Ensure all structural nodes from fs_report_master are present in fs_report_details
            INSERT INTO "{config.SCHEMANAME}".fs_report_details (
                tb_id,
                fs_type,
                fs_node_id,
                fs_node_name,
                parent_fs_node_id,
                node_seq,
                reporting_node_flag,
                balance
            )
            SELECT
                p_tb_id,
                frm.fs_type,
                frm.fs_node_id,
                frm.fs_node_name,
                frm.parent_fs_node_id,
                frm.node_seq,
                frm.reporting_node_flag,
                0.00
            FROM "{config.SCHEMANAME}".fs_report_master frm
            WHERE frm.company_id = (SELECT company_id FROM "{config.SCHEMANAME}".trial_balance WHERE tb_id = p_tb_id)
            ON CONFLICT (tb_id, fs_node_id) DO UPDATE SET
                fs_type = EXCLUDED.fs_type,
                fs_node_name = EXCLUDED.fs_node_name,
                parent_fs_node_id = EXCLUDED.parent_fs_node_id,
                node_seq = EXCLUDED.node_seq,
                reporting_node_flag = EXCLUDED.reporting_node_flag;

            -- 2. Populate leaf/reporting nodes (reporting_node_flag = true) using COA hierarchy
            UPDATE "{config.SCHEMANAME}".fs_report_details fd
            SET balance = COALESCE((
                WITH RECURSIVE coa_hierarchy AS (
                    SELECT coa.coa_node_id, coa.coa_node_name, coa.posting_ledger_flag
                    FROM "{config.SCHEMANAME}".fs_report_master frm
                    JOIN "{config.SCHEMANAME}".coa_master coa ON coa.coa_node_id = frm.mapped_coa_node_id
                    WHERE frm.fs_node_id = fd.fs_node_id

                    UNION ALL

                    SELECT child.coa_node_id, child.coa_node_name, child.posting_ledger_flag
                    FROM "{config.SCHEMANAME}".coa_master child
                    JOIN coa_hierarchy parent ON child.parent_coa_node_id = parent.coa_node_id
                )
                SELECT SUM(tbd.closing_balance)
                FROM coa_hierarchy ch
                JOIN "{config.SCHEMANAME}".trial_balance_details tbd ON tbd.account_name = ch.coa_node_name
                WHERE tbd.tb_id = fd.tb_id AND ch.posting_ledger_flag = TRUE
            ), 0.00)
            WHERE fd.tb_id = p_tb_id AND fd.reporting_node_flag = TRUE;

            -- 2b. Fallback: If mapped_coa_node_id is NULL, match fs_node_name directly with account_name
            UPDATE "{config.SCHEMANAME}".fs_report_details fd
            SET balance = COALESCE((
                SELECT SUM(tbd.closing_balance)
                FROM "{config.SCHEMANAME}".trial_balance_details tbd
                WHERE tbd.tb_id = fd.tb_id AND tbd.account_name = fd.fs_node_name
            ), 0.00)
            WHERE fd.tb_id = p_tb_id
              AND fd.reporting_node_flag = TRUE
              AND (
                  SELECT mapped_coa_node_id
                  FROM "{config.SCHEMANAME}".fs_report_master
                  WHERE fs_node_id = fd.fs_node_id
              ) IS NULL;

            -- 3. Bottom-up rollup for parent/group nodes (reporting_node_flag = false)
            LOOP
                UPDATE "{config.SCHEMANAME}".fs_report_details parent
                SET balance = COALESCE((
                    SELECT SUM(child.balance)
                    FROM "{config.SCHEMANAME}".fs_report_details child
                    WHERE child.parent_fs_node_id = parent.fs_node_id
                      AND child.tb_id = parent.tb_id
                ), 0.00)
                WHERE parent.tb_id = p_tb_id
                  AND parent.reporting_node_flag = FALSE
                  AND parent.balance IS DISTINCT FROM COALESCE((
                      SELECT SUM(child.balance)
                      FROM "{config.SCHEMANAME}".fs_report_details child
                      WHERE child.parent_fs_node_id = parent.fs_node_id
                        AND child.tb_id = parent.tb_id
                  ), 0.00);

                GET DIAGNOSTICS v_rows_updated = ROW_COUNT;
                EXIT WHEN v_rows_updated = 0;
            END LOOP;

        END;
        $$ LANGUAGE plpgsql;
        """
        cursor.execute(create_function_query)

        # Run the PL/pgSQL balance calculation for each unique tb_id in the uploaded batch
        unique_tb_ids = list(set(r["tb_id"] for r in processed_records))
        for tb_id in unique_tb_ids:
            cursor.execute(f'SELECT "{config.SCHEMANAME}".calculate_fs_report_details(%s)', (tb_id,))

        if own_connection:
            conn.commit()

        logger.info(
            f"Successfully inserted/updated {len(processed_records)} records in fs_report_details and recalculated balances."
        )

        response_body = {
            "message": "Data inserted/updated successfully and balances recalculated via PL/SQL",
            "count": len(processed_records)
        }

        return (config.STATUS_SUCCESS, config.DESC_MSG0007, None, response_body)

    except utils.CustomValidationException as e:
        if conn and own_connection:
            conn.rollback()
        return e.status_code, e.status_description, e.error_message, None

    except Exception as e:
        logger.error(f"Error inserting fs_report_details: {e}")
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
