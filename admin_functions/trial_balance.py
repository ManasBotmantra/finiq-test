"""Business logic for Trial Balance operations."""

import logging
import uuid
from psycopg2.extras import execute_values
from common_functions import config, utils

logger = logging.getLogger(__name__)


def f_insert_trial_balance(records: list, connection=None) -> tuple:
    """
    Inserts or upserts records into the trial_balance table.

    Args:
        records:      List of dictionaries to insert.
        connection:   Active database connection. If None, a new one will be opened.

    Returns:
        tuple: (status_code, status_description, error_message, response_body)
    """
    conn = connection
    cursor = None
    own_connection = False

    try:
        if not isinstance(records, list) or not records:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "records must be a non-empty list of dictionaries"
            )

        mandatory_fields = ["tb_id", "company_id", "tb_name", "from_date", "to_date"]
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
                        f"Missing mandatory field '{field}' at index {idx}"
                    )

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

        query = f"""
            INSERT INTO "{config.SCHEMANAME}".trial_balance (
                tb_id,
                company_id,
                tb_name,
                from_date,
                to_date
            ) VALUES %s
            ON CONFLICT (tb_id)
            DO UPDATE SET
                company_id = EXCLUDED.company_id,
                tb_name = EXCLUDED.tb_name,
                from_date = EXCLUDED.from_date,
                to_date = EXCLUDED.to_date;
        """

        values = [
            (
                r.get('tb_id'),
                r.get('company_id'),
                r.get('tb_name'),
                r.get('from_date'),
                r.get('to_date')
            )
            for r in records
        ]

        execute_values(cursor, query, values)

        if own_connection:
            conn.commit()

        response_body = {
            "message": "Data inserted/updated successfully",
            "count": len(records)
        }
        return (config.STATUS_SUCCESS, config.DESC_MSG0007, None, response_body)

    except utils.CustomValidationException as e:
        if conn and own_connection:
            conn.rollback()
        return e.status_code, e.status_description, e.error_message, None
    except Exception as e:
        logger.error(f"Error inserting trial_balance: {e}")
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


def f_insert_trial_balance_details(records: list, connection=None) -> tuple:
    """
    Inserts or upserts records into the trial_balance_details table.

    Args:
        records:      List of dictionaries to insert.
        connection:   Active database connection. If None, a new one will be opened.

    Returns:
        tuple: (status_code, status_description, error_message, response_body)
    """
    conn = connection
    cursor = None
    own_connection = False

    try:
        if not isinstance(records, list) or not records:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "records must be a non-empty list of dictionaries"
            )

        mandatory_fields = ["tb_id", "account_name", "closing_balance"]
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
                        f"Missing mandatory field '{field}' at index {idx}"
                    )

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

        query = f"""
            INSERT INTO "{config.SCHEMANAME}".trial_balance_details (
                tb_id,
                account_name,
                account_code,
                opening_balance,
                debit,
                credit,
                closing_balance
            ) VALUES %s
            ON CONFLICT (tb_id, account_name)
            DO UPDATE SET
                account_code = EXCLUDED.account_code,
                opening_balance = EXCLUDED.opening_balance,
                debit = EXCLUDED.debit,
                credit = EXCLUDED.credit,
                closing_balance = EXCLUDED.closing_balance;
        """

        values = [
            (
                r.get('tb_id'),
                r.get('account_name'),
                r.get('account_code'),
                r.get('opening_balance'),
                r.get('debit'),
                r.get('credit'),
                r.get('closing_balance')
            )
            for r in records
        ]

        execute_values(cursor, query, values)

        if own_connection:
            conn.commit()

        response_body = {
            "message": "Data inserted/updated successfully",
            "count": len(records)
        }
        return (config.STATUS_SUCCESS, config.DESC_MSG0007, None, response_body)

    except utils.CustomValidationException as e:
        if conn and own_connection:
            conn.rollback()
        return e.status_code, e.status_description, e.error_message, None
    except Exception as e:
        logger.error(f"Error inserting trial_balance_details: {e}")
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


def f_insert_trial_balance_with_details(
    company_id: str,
    tb_name: str,
    from_date: str,
    to_date: str,
    details: list,
    creator_user_id: str = None
) -> tuple:
    """
    Inserts a Trial Balance record and its details inside a single database transaction.

    Args:
        company_id:      UUID of the company (must exist in company_master).
        tb_name:         Name of the Trial Balance (Unique).
        from_date:       Start date of the Trial Balance.
        to_date:         End date of the Trial Balance.
        details:         List of dictionaries containing details:
                         - account_name (str, Mandatory)
                         - account_code (str, Optional/Nullable)
                         - opening_balance (numeric, Optional/Nullable)
                         - debit (numeric, Optional/Nullable)
                         - credit (numeric, Optional/Nullable)
                         - closing_balance (numeric, Mandatory)
        creator_user_id: Optional ID of the user performing the operation.

    Returns:
        tuple: (status_code, status_description, error_message, response_body)
    """
    conn = None
    cursor = None

    try:
        # -----------------------------------------------------------------
        # 1. Validate Input Types and Formats
        # -----------------------------------------------------------------
        if not company_id or not isinstance(company_id, str):
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "company_id is required and must be a string"
            )

        if not tb_name or not isinstance(tb_name, str):
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "tb_name is required and must be a string"
            )

        if not from_date or not to_date:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "both from_date and to_date are required"
            )

        if not isinstance(details, list) or not details:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "details must be a non-empty list of dictionaries"
            )

        # -----------------------------------------------------------------
        # 2. Database Connection
        # -----------------------------------------------------------------
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                config.ERR_MSG0010
            )

        cursor = conn.cursor()

        # -----------------------------------------------------------------
        # 3. Validate company_id exists in company_master
        # -----------------------------------------------------------------
        cursor.execute(
            f'SELECT company_id FROM "{config.SCHEMANAME}".company_master WHERE company_id = %s',
            (company_id,)
        )
        if cursor.fetchone() is None:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                config.ERR_MSG0181.format(company_id=company_id)
            )

        # -----------------------------------------------------------------
        # 4. Generate tb_id (PK)
        # -----------------------------------------------------------------
        tb_id = str(uuid.uuid4())

        # -----------------------------------------------------------------
        # 5. Insert into trial_balance
        # -----------------------------------------------------------------
        tb_record = {
            "tb_id": tb_id,
            "company_id": company_id,
            "tb_name": tb_name,
            "from_date": from_date,
            "to_date": to_date
        }
        status, desc, err, _ = f_insert_trial_balance([tb_record], connection=conn)
        if status != config.STATUS_SUCCESS:
            raise utils.CustomValidationException(status, desc, err)

        # -----------------------------------------------------------------
        # 6. Insert into trial_balance_details
        # -----------------------------------------------------------------
        details_records = []
        for r in details:
            details_records.append({
                "tb_id": tb_id,
                "account_name": r.get('account_name'),
                "account_code": r.get('account_code'),
                "opening_balance": r.get('opening_balance'),
                "debit": r.get('debit'),
                "credit": r.get('credit'),
                "closing_balance": r.get('closing_balance')
            })

        status, desc, err, _ = f_insert_trial_balance_details(details_records, connection=conn)
        if status != config.STATUS_SUCCESS:
            raise utils.CustomValidationException(status, desc, err)

        # -----------------------------------------------------------------
        # 7. Commit Transaction
        # -----------------------------------------------------------------
        conn.commit()

        logger.info(f"Trial Balance created: {tb_id} with {len(details)} details.")

        response_body = {
            "tb_id": tb_id,
            "details_count": len(details)
        }

        return (
            config.STATUS_SUCCESS,
            config.DESC_MSG0007,
            None,
            response_body
        )

    except utils.CustomValidationException as e:
        if conn:
            conn.rollback()
        return e.status_code, e.status_description, e.error_message, None

    except Exception as e:
        logger.error(f"Error creating Trial Balance: {e}")
        if conn:
            conn.rollback()
        return (
            config.STATUS_SYSTEM_EXCEPTION,
            config.DESC_MSG0004,
            str(e),
            None
        )

    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as close_err:
            logger.error(f"Error closing cursor or connection: {close_err}")
