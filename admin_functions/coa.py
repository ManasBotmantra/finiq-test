"""Business logic for Chart of Accounts (COA) node operations."""

import uuid
import logging

from common_functions import config
from common_functions.db_connection import get_cursor

logger = logging.getLogger(__name__)


def f_create_coa_node(
    company_id: str,
    coa_node_code: str,
    coa_node_name: str,
    parent_coa_node_id: str,
    posting_ledger_flag: bool
) -> tuple:
    """
    Inserts a new COA node into the coa_master table.

    Args:
        company_id:          UUID of the company (must exist in company_master).
        coa_node_code:       Optional short code for the node (e.g. "1000").
        coa_node_name:       Optional display name (e.g. "Cash & Bank").
        parent_coa_node_id:  UUID of the parent node, or None/empty for root.
        posting_ledger_flag: True = Posting Ledger, False = Group.

    Returns:
        tuple: (status_code, status_description, error_message, coa_node_id)
    """
    try:
        with get_cursor() as cur:

            # -----------------------------------------------------------------
            # 1. Validate company_id exists in company_master
            # -----------------------------------------------------------------
            cur.execute(
                "SELECT company_id FROM company_master WHERE company_id = %s",
                (company_id,)
            )
            if cur.fetchone() is None:
                return (
                    config.STATUS_INVALID_INPUT,
                    config.DESC_MSG0006,
                    config.ERR_MSG0007,
                    None
                )

            # -----------------------------------------------------------------
            # 2. Validate parent_coa_node_id (if provided)
            # -----------------------------------------------------------------
            if parent_coa_node_id:
                cur.execute(
                    "SELECT coa_node_id FROM coa_master WHERE coa_node_id = %s",
                    (parent_coa_node_id,)
                )
                if cur.fetchone() is None:
                    return (
                        config.STATUS_INVALID_INPUT,
                        config.DESC_MSG0006,
                        config.ERR_MSG0008,
                        None
                    )

            # -----------------------------------------------------------------
            # 3. Check for duplicate (same company + same node name)
            # -----------------------------------------------------------------
            if coa_node_name:
                cur.execute(
                    """
                    SELECT coa_node_id FROM coa_master
                    WHERE company_id = %s AND coa_node_name = %s
                    """,
                    (company_id, coa_node_name)
                )
                if cur.fetchone() is not None:
                    return (
                        config.STATUS_DUPLICATE,
                        config.DESC_MSG0003,
                        config.ERR_MSG0012,
                        None
                    )

            # -----------------------------------------------------------------
            # 4. Generate coa_node_id (PK)
            # -----------------------------------------------------------------
            coa_node_id = str(uuid.uuid4())

            # -----------------------------------------------------------------
            # 5. Insert into coa_master
            # -----------------------------------------------------------------
            cur.execute(
                """
                INSERT INTO coa_master (
                    coa_node_id,
                    company_id,
                    coa_node_code,
                    coa_node_name,
                    parent_coa_node_id,
                    posting_ledger_flag
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    coa_node_id,
                    company_id,
                    coa_node_code if coa_node_code else None,
                    coa_node_name if coa_node_name else None,
                    parent_coa_node_id if parent_coa_node_id else None,
                    posting_ledger_flag
                )
            )

            logger.info(f"COA node created: {coa_node_id} for company {company_id}")

            return (
                config.STATUS_SUCCESS,
                config.DESC_MSG0002,
                config.ERR_MSG0002,
                coa_node_id
            )

    except Exception as e:
        logger.error(f"Error creating COA node: {e}")
        return (
            config.STATUS_SYSTEM_EXCEPTION,
            config.DESC_MSG0004,
            str(e),
            None
        )
