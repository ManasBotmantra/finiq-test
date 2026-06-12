"""This module provides functions for user authorization, including generating, validating, and renewing JWT tokens."""

import datetime
from zoneinfo import ZoneInfo

import jwt

from . import config, password_utlis, utils


def f_generate_authorize_token(user_id_or_key, for_email=False,is_key_based=False):
    try:
        if not user_id_or_key:
            return "", "ERROR"

        current_time = datetime.datetime.now(datetime.timezone.utc)
        if for_email:
            expiry_time = current_time + \
                datetime.timedelta(seconds=config.EMAIL_TOKEN_EXPIRY_LIMIT)
        else:
            expiry_time = current_time + \
                datetime.timedelta(seconds=config.TOKEN_EXPIRY_LIMIT)
        if is_key_based:
            payload = {
                "key": user_id_or_key,
                "iat": current_time,
                "exp": expiry_time
            }
        else:
            payload = {
                "user_id": user_id_or_key,
                "iat": current_time,
                "exp": expiry_time
            }

        token = jwt.encode(payload, config.SECRET_KEY,
                           algorithm=config.JWT_ALGORITHM)
        return token, "SUCCESS"

    except Exception:
        return "", "ERROR"


def f_validate_user(user_id, password):
    """
    Validates a user's credentials and returns an authenticationorization token.

    Request:
        Parameters:
            user_id (str): The user's ID
            password (str): The user's password
    Returns:
        dict: API response with new authorization token and org names
    """

    try:
        # Step 1: Validate inputs
        if not user_id or not password:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                config.ERR_MSG0002
            )

        # Step 2: Connect to database
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0009,
                config.ERR_MSG0010
            )

        cursor = conn.cursor()

        # ✅ Step 3: Fetch user by ID only (not by password)
        query = f"""
            SELECT um.user_id, um.password, um.name, um.role, um.user_status,
                    COALESCE(uom.org_name, '') as org_name
            FROM "{config.SCHEMANAME}"."user_master" um
            LEFT JOIN "{config.SCHEMANAME}"."user_org_master" uom ON um.user_id = uom.user_id
            WHERE um.user_id = %s AND LOWER(um.user_status) = 'active'
        """
        cursor.execute(query, (user_id,))
        records = cursor.fetchall()

        if not records:
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                config.ERR_MSG0003
            )
        # ✅ Step 4: Validate password using bcrypt
        _, hashed_pw, _, _, _, _ = records[0]
        if not password_utlis.check_password(password, hashed_pw):
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                "Incorrect password"
            )

        # Step 6: Generate token
        authorization_token, token_status = f_generate_authorize_token(user_id)
        if token_status == "ERROR" or not authorization_token:
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                config.ERR_MSG0004
            )

        # Step 7: Prepare response
        response_body = {
            "authorize_token": authorization_token
        }

        status_code = config.STATUS_SUCCESS
        status_desc = config.DESC_MSG0007
        error_msg = ""

    except utils.CustomValidationException as e:
        status_code = e.status_code
        status_desc = e.status_description
        error_msg = e.error_message
        response_body = None

    except Exception as e:
        status_code = config.STATUS_SYSTEM_EXCEPTION
        status_desc = config.DESC_MSG0004
        error_msg = str(e)
        response_body = None

    finally:
        # Step 8: Ensure DB resources are closed and audit is logged
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass

    # Step 9: Return final response
    return utils.f_generate_response(status_code, status_desc, error_msg, response_body)

def f_renew_authorization_token(authorization_token):
    """
    Renews the user's JWT authorize_token if the existing token is valid.
    Token expiration is automatically validated by JWT library during decryption.

    Args:
        authorization_token (str): The JWT token to be renewed.

    Returns:
        tuple: (dict with API response, user_id)
    """
    user_id = None
    try:
        # Step 1: Validate input
        if not authorization_token:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                config.ERR_MSG0109
            )

        # Step 2: Decrypt and validate token (JWT library automatically checks expiration)
        token_data = f_decrypt_authorize_token(authorization_token)
        if token_data.get("status") != "SUCCESS":
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                config.ERR_MSG0007
            )

        user_id = token_data.get("user_id")

        # Step 3: DB Connection
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0009,
                config.ERR_MSG0010
            )

        cursor = conn.cursor()

        try:
            # Step 4: Check user status
            query = f"""
                SELECT user_status
                FROM "{config.SCHEMANAME}"."user_master"
                WHERE user_id = %s
            """
            cursor.execute(query, (user_id,))
            records = cursor.fetchall()
            user_status = records[0][0] if records else None

            if not user_status or user_status.strip().lower() != "active":
                raise utils.CustomValidationException(
                    config.STATUS_AUTHENTICATION_FAILED,
                    config.DESC_MSG0005,
                    config.ERR_MSG0111
                )

            # Step 5: Generate new token
            new_token, token_status = f_generate_authorize_token(user_id)
            if token_status == "ERROR":
                raise utils.CustomValidationException(
                    config.STATUS_AUTHENTICATION_FAILED,
                    config.DESC_MSG0005,
                    config.ERR_MSG0112
                )

            # Step 6: Prepare response
            response_body = {
                "authorize_token": new_token
            }

            status_code = config.STATUS_SUCCESS
            status_desc = config.DESC_MSG0007
            error_msg = ""

        finally:
            cursor.close()
            conn.close()

    except utils.CustomValidationException as e:
        status_code = e.status_code
        status_desc = e.status_description
        error_msg = e.error_message
        response_body = None

    except Exception as e:
        status_code = config.STATUS_SYSTEM_EXCEPTION
        status_desc = config.DESC_MSG0004
        error_msg = str(e)
        response_body = None

    return utils.f_generate_response(status_code, status_desc, error_msg, response_body), user_id


def f_decrypt_authorize_token(authorization_token):
    """
    Decodes a given JWT authorization token and returns the embedded user_id and timestamp
    if the token is valid. Otherwise, returns an error response.

    Args:
        authorization_token (str): JWT authorization token

    Returns:
        dict: Response with status, user_id, and timestamp
    """

    try:
        if not authorization_token:
            return {
                "status": "ERROR",
                "user_id": "",
                "timestamp": ""
            }

        payload = jwt.decode(
            authorization_token, config.SECRET_KEY, algorithms=config.JWT_ALGORITHM)
        user_id = payload.get("user_id")

        return {
            "status": "SUCCESS",
            "user_id": user_id,
            "timestamp": str(payload.get("iat"))
        }

    except jwt.ExpiredSignatureError:
        return {
            "status": "ERROR",
            "user_id": "",
            "timestamp": ""
        }

    except jwt.InvalidTokenError:
        return {
            "status": "ERROR",
            "user_id": "",
            "timestamp": ""
        }


def f_decrypt_authorize_token_with_key(authorization_token, is_key_based=True):

    """
    Decodes a given JWT authorization token and returns the embedded user_id and timestamp
    if the token is valid. Otherwise, returns an error response.

    Args:
        authorization_token (str): JWT authorization token

    Returns:
        dict: Response with status, user_id, and timestamp
    """

    try:
        key_based_flag = False

        if not authorization_token:
            return {
                "status": "ERROR",
                "user_id": "",
                "timestamp": "",
                "is_key_based": key_based_flag
            }

        payload = jwt.decode(authorization_token, config.SECRET_KEY, algorithms=config.JWT_ALGORITHM)
        user_id = payload.get("user_id")

        if not user_id:
            if is_key_based:
                key_based_flag = True
                key = payload.get("key")
                if not key:
                    return {
                        "status": "ERROR",
                        "user_id": "",
                        "timestamp": "",
                        "is_key_based": key_based_flag
                    }
                user_id = key
            else:
                return {
                    "status": "ERROR",
                    "user_id": "",
                    "timestamp": "",
                    "is_key_based": key_based_flag
                }

        return {
            "status": "SUCCESS",
            "user_id": user_id,
            "timestamp": str(payload.get("iat")),
            "is_key_based": key_based_flag

        }

    except jwt.ExpiredSignatureError:
        return {
            "status": "ERROR",
            "user_id": "",
            "timestamp": "",
            "is_key_based": key_based_flag
        }

    except jwt.InvalidTokenError:
        return {
            "status": "ERROR",
            "user_id": "",
            "timestamp": "",
            "is_key_based": key_based_flag
        }

def f_validate_authorize_token(authorization_token):
    """
    Validates a JWT token by checking its existence and decryption status.
    Token expiration is automatically validated by JWT library.

    Returns:
        tuple: ("SUCCESS"/"ERROR", user_id or None)
    """
    try:
        # Step 1: Check if token is present
        if not authorization_token:
            return "ERROR", None

        # Step 2: Decrypt token (JWT library automatically validates expiration)
        token_data = f_decrypt_authorize_token(authorization_token)
        if token_data.get("status") != "SUCCESS":
            return "ERROR", None

        # Step 3: Return success with user_id
        user_id = token_data.get("user_id")
        if user_id:
            return "SUCCESS", user_id

        return "ERROR", None

    except Exception:
        return "ERROR", None


def f_validate_authorize_token_with_key(authorization_token):
    """
    Validates a JWT token by checking its existence and decryption status.
    Token expiration is automatically validated by JWT library.

    Returns:
        tuple: ("SUCCESS"/"ERROR", user_id or None, key_based_flag)
    """
    try:
        key_based_flag = False
        # Step 1: Check if token is present
        if not authorization_token:
            return "ERROR", None, key_based_flag

        # Step 2: Decrypt token (JWT library automatically validates expiration)
        token_data = f_decrypt_authorize_token_with_key(authorization_token, is_key_based=True)
        if token_data.get("status") != "SUCCESS":
            return "ERROR", None, key_based_flag

        # Step 3: Return success with user_id
        user_id_or_key = token_data.get("user_id")
        key_based_flag = token_data.get("is_key_based")
        if user_id_or_key:
            return "SUCCESS", user_id_or_key, key_based_flag

        return "ERROR", None, key_based_flag

    except Exception:
        return "ERROR", None, key_based_flag


def f_validate_key(key: str, org_name: str):
    """
    Validates a key and returns an authorization token.

    Parameters:
        key (str): API key
        org_name (str): Organization name

    Returns:
        dict: API response with authorization token and status

    Raises:
        utils.CustomValidationException if key or organization name is invalid or inactive
    """
    conn = None
    cursor = None

    try:
        # ------------------ 1️⃣ Input Validation ------------------
        if not key or not org_name:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Key or Organization name missing"
            )

        # ------------------ 2️⃣ DB Connection ------------------
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0009,
                config.ERR_MSG0010
            )

        cursor = conn.cursor()

        # ------------------ 3️⃣ Validate Org + Key ------------------
        # Conditions:
        # org_master.org_status = ACTIVE
        # org_credentials.cred_type = CRED-TYPE
        # org_credentials.cred_sub_type = KEY-LIST
        # org_credentials.cred_type_status = ACTIVE
        # JSONB contains key with ACTIVE status
        query = f"""
            SELECT 1
            FROM "{config.SCHEMANAME}"."org_master" om
            JOIN "{config.SCHEMANAME}"."org_credentials" oc
                ON om.org_name = oc.org_name
            WHERE om.org_name = %s
              AND LOWER(om.org_status) = 'active'
              AND LOWER(oc.cred_type) = 'key'
              AND LOWER(oc.cred_sub_type) = 'key-list'
              AND LOWER(oc.cred_type_status) = 'active'
              AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(oc.cred_json) elem
                    WHERE elem ->> 'key' = %s
                      AND LOWER(elem ->> 'status') = 'active'
              );
        """

        cursor.execute(query, (org_name, key))
        record = cursor.fetchone()

        if not record:
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                "Invalid organization or inactive/invalid key"
            )

        # ------------------ 4️⃣ Generate Authorization Token ------------------
        authorization_token, token_status = f_generate_authorize_token(
            key,
            is_key_based=True
        )

        if token_status == "ERROR" or not authorization_token:
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                config.ERR_MSG0004
            )

        # ------------------ 5️⃣ Success Response ------------------
        response_body = {
            "authorize_token": authorization_token
        }

        status_code = config.STATUS_SUCCESS
        status_desc = config.DESC_MSG0007
        error_msg = ""

    # ------------------ 6️⃣ Known Validation Errors ------------------
    except utils.CustomValidationException as e:
        status_code = e.status_code
        status_desc = e.status_description
        error_msg = e.error_message
        response_body = None

    # ------------------ 7️⃣ Unexpected Errors ------------------
    except Exception as e:
        status_code = config.STATUS_SYSTEM_EXCEPTION
        status_desc = config.DESC_MSG0004
        error_msg = str(e)
        response_body = None

    finally:
        # ------------------ 8️⃣ Cleanup ------------------
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass

    # ------------------ 9️⃣ Final Response ------------------
    return utils.f_generate_response(status_code, status_desc, error_msg, response_body)


def f_forgot_password(str_user_id: str):
    """
    Sends a password reset email to the user if they exist and are active.

    Args:
        str_user_id (str): The user's email/ID

    Returns:
        tuple: (status_code, status_description, error_message)
    """
    try:
        # Step 1: Validate input
        if not str_user_id or not isinstance(str_user_id, str) or not str_user_id.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "User ID is required and must be a non-empty string"
            )

        str_user_id = str_user_id.strip()

        # Step 2: Connect to database
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0009,
                config.ERR_MSG0010
            )

        cursor = conn.cursor()

        try:
            # Step 3: Check if user exists and is active
            query = f"""
                SELECT user_id, name
                FROM "{config.SCHEMANAME}".user_master
                WHERE user_id = %s AND LOWER(user_status) = 'active'
            """
            cursor.execute(query, (str_user_id,))
            record = cursor.fetchone()

            if not record:
                raise utils.CustomValidationException(
                    config.STATUS_NO_DATA_FOUND,
                    config.DESC_MSG0003,
                    "User not found or account is not active"
                )

            user_id, user_name = record

            # Step 4: Generate password reset token (with email expiry)
            reset_token, token_status = f_generate_authorize_token(user_id, for_email=True)
            if token_status == "ERROR" or not reset_token:
                raise utils.CustomValidationException(
                    config.STATUS_SYSTEM_EXCEPTION,
                    config.DESC_MSG0004,
                    "Failed to generate password reset token"
                )

            # Step 5: Prepare email content
            reset_url = f"{config.FRONTEND_RESET_URL}?token={reset_token}"

            email_subject = "Password Reset Request"
            email_body = f"""
            <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>Hello {user_name},</p>
                <p>We received a request to reset your password. Click the link below to reset your password:</p>
                <p><a href="{reset_url}">Reset Password</a></p>
                <p>This link will expire in {config.EMAIL_TOKEN_EXPIRY_LIMIT // 60} minutes.</p>
                <p>If you did not request a password reset, please ignore this email.</p>
                <br>
                <p>Best regards,<br>Support Team</p>
            </body>
            </html>
            """

            # Step 6: Send email
            smtp_config = {
                "SMTP_SERVER": config.SMTP_SERVER,
                "SMTP_PORT": config.SMTP_PORT,
                "SMTP_USERNAME": config.SMTP_USERNAME,
                "SMTP_PASSWORD": config.SMTP_PASSWORD,
                "SMTP_FROM_EMAIL": config.SMTP_FROM_EMAIL
            }

            from common_functions import email_utils
            email_success, email_message = email_utils.f_send_email(
                smtp_config=smtp_config,
                to=[user_id],
                subject=email_subject,
                body=email_body,
                html=True
            )

            if not email_success:
                raise utils.CustomValidationException(
                    config.STATUS_SYSTEM_EXCEPTION,
                    config.DESC_MSG0004,
                    f"Failed to send password reset email: {email_message}"
                )

            # Step 7: Success response (no body for security)
            status_code = config.STATUS_SUCCESS
            status_description = config.DESC_MSG0007
            error_message = ""

        finally:
            cursor.close()
            conn.close()

    except utils.CustomValidationException as e:
        status_code = e.status_code
        status_description = e.status_description
        error_message = e.error_message

    except Exception as e:
        status_code = config.STATUS_SYSTEM_EXCEPTION
        status_description = config.DESC_MSG0004
        error_message = str(e)

    return status_code, status_description, error_message

def f_reset_password(token: str, new_password: str):
    """
    Resets the user's password using a valid password reset token.

    Args:
        token (str): JWT token from the password reset email
        new_password (str): New password to set for the user

    Returns:
        tuple: (status_code, status_description, error_message)
    """
    try:
        # Step 1: Validate inputs
        if not token or not isinstance(token, str) or not token.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Token is required and must be a non-empty string"
            )

        if not new_password or not isinstance(new_password, str) or not new_password.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "New password is required and must be a non-empty string"
            )

        token = token.strip()
        new_password = new_password.strip()

        # Validate password strength
        if len(new_password) < 8:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Password must be at least 8 characters long"
            )

        # Step 2: Decrypt and validate token (JWT library automatically checks expiration)
        token_data = f_decrypt_authorize_token(token)
        if token_data.get("status") != "SUCCESS":
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                "Invalid or expired password reset token"
            )

        user_id = token_data.get("user_id")
        if not user_id:
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                "Invalid token: user_id not found"
            )

        # Step 3: Connect to database
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0009,
                config.ERR_MSG0010
            )

        cursor = conn.cursor()

        try:
            # Step 4: Check if user exists and is active (combined in one query)
            query = f"""
                SELECT user_id
                FROM "{config.SCHEMANAME}".user_master
                WHERE user_id = %s AND LOWER(user_status) = 'active'
            """
            cursor.execute(query, (user_id,))
            record = cursor.fetchone()

            if not record:
                raise utils.CustomValidationException(
                    config.STATUS_AUTHENTICATION_FAILED,
                    config.DESC_MSG0005,
                    "User not found or account is not active"
                )

            # Step 5: Hash the new password
            hashed_password = password_utlis.hash_password(new_password)

            # Step 6: Update password in database
            update_query = f"""
                UPDATE "{config.SCHEMANAME}".user_master
                SET password = %s
                WHERE user_id = %s
            """
            cursor.execute(update_query, (hashed_password, user_id))
            conn.commit()

            if cursor.rowcount == 0:
                raise utils.CustomValidationException(
                    config.STATUS_SYSTEM_EXCEPTION,
                    config.DESC_MSG0004,
                    "Failed to update password"
                )

            # Step 7: Success response (no body for security)
            status_code = config.STATUS_SUCCESS
            status_description = config.DESC_MSG0007
            error_message = ""

        finally:
            cursor.close()
            conn.close()

    except utils.CustomValidationException as e:
        status_code = e.status_code
        status_description = e.status_description
        error_message = e.error_message

    except Exception as e:
        status_code = config.STATUS_SYSTEM_EXCEPTION
        status_description = config.DESC_MSG0004
        error_message = str(e)

    return status_code, status_description, error_message


def f_change_password(str_user_id: str, str_current_password: str, str_new_password: str):
    """
    Updates a user's password after validating the current password.

    Steps:
        1. Fetch stored hashed password from user_master.
        2. Validate current password using check_password().
        3. Hash the new password using hash_password().
        4. Update user_master table.

    Returns:
        Tuple (status_code, status_description, error_message)
    """

    conn = None
    cursor = None

    try:
        if not str_current_password:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Current Password is required."
            )

        if not str_new_password:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "New Password is required."
            )

        # Validate password strength
        if len(str_new_password) < 8:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Password must be at least 8 characters long"
            )

        # ---------------- DB CONNECT ----------------
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0009,
                config.ERR_MSG0010
            )

        cursor = conn.cursor()

        # ---------------- FETCH STORED HASH ----------------
        cursor.execute(
            f"""
            SELECT password
            FROM "{config.SCHEMANAME}".user_master
            WHERE LOWER(user_id) = %s AND LOWER(user_status) = 'active'
            """,
            (str_user_id.lower(),)
        )

        row = cursor.fetchone()

        if not row:
            raise utils.CustomValidationException(
                config.STATUS_NO_DATA_FOUND,
                config.DESC_MSG0003,
                "User not found or inactive"
            )

        stored_hashed_password = row[0]

        # ---------------- VALIDATE CURRENT PASSWORD ----------------
        is_valid = password_utlis.check_password(
            plain_password=str_current_password,
            hashed_password=stored_hashed_password
        )

        if not is_valid:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Current password is incorrect"
            )

        # ---------------- HASH NEW PASSWORD ----------------
        new_hashed_password = password_utlis.hash_password(str_new_password)

        # ---------------- UPDATE NEW PASSWORD IN DB ----------------
        cursor.execute(
            f"""
            UPDATE "{config.SCHEMANAME}".user_master
            SET password = %s
            WHERE LOWER(user_id) = %s
            """,
            (new_hashed_password, str_user_id.lower())
        )

        conn.commit()

        return config.STATUS_SUCCESS, config.DESC_MSG0007, ""

    except utils.CustomValidationException as e:
        return e.status_code, e.status_description, e.error_message

    except Exception as e:
        return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e)

    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass


def f_is_user_authorised(entity_code, org_name, user_email, company_id=None, based_on=None):
    """
    Checks if a user is authorized to access a specific module based on their role.
    Validates that the organization, module, org_module, company, and company_module are active.

    Role-based authorization logic:
    - SUPER ADMIN: Always authorized (after hierarchy status checks)
    - ADMIN / USER: Must be associated with the organization in user_org_master

    Args:
        entity_code (str): The module_code to check access for
        org_name (str): The organization name
        user_email (str): The user's email/user_id
        company_id (str, optional): The company ID to validate
        based_on (str, optional): Deprecated parameter, kept for backward compatibility

    Returns:
        tuple: (status_code, status_description, error_message)
    """
    conn = None
    cursor = None
    try:
        # Step 1: Input validation
        if not entity_code or not isinstance(entity_code, str) or not entity_code.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Module code is required and must be a non-empty string"
            )

        if not org_name or not isinstance(org_name, str) or not org_name.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Organization name is required and must be a non-empty string"
            )

        if not user_email or not isinstance(user_email, str) or not user_email.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "User email is required and must be a non-empty string"
            )

        # Clean inputs
        module_code = entity_code.strip()
        org_name = org_name.strip()
        user_email = user_email.strip()
        if company_id:
            company_id = company_id.strip()

        # Step 2: Connect to database
        conn = utils.f_connect_to_db()
        if not conn:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0009,
                config.ERR_MSG0010
            )
        cursor = conn.cursor()

        # Step 3: Get user role and status from user_master
        query = f"""
            SELECT role
            FROM "{config.SCHEMANAME}".user_master
            WHERE user_id = %s AND LOWER(user_status) = 'active'
        """
        cursor.execute(query, (user_email,))
        user_record = cursor.fetchone()

        if not user_record:
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                f"User '{user_email}' not found or inactive"
            )
            
        user_role = user_record[0].strip().upper()

        # Step 4: Check if organization is active in org_master
        query = f"""
            SELECT 1
            FROM "{config.SCHEMANAME}".org_master
            WHERE org_name = %s AND LOWER(org_status) = 'active'
        """
        cursor.execute(query, (org_name,))
        if not cursor.fetchone():
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                f"Organization '{org_name}' not found or inactive"
            )

        # Step 5: Role-based organization association check
        if user_role in ("ADMIN", "USER"):
            query = f"""
                SELECT 1
                FROM "{config.SCHEMANAME}".user_org_master
                WHERE user_id = %s AND org_name = %s
            """
            cursor.execute(query, (user_email, org_name))
            org_association = cursor.fetchone()

            if not org_association:
                raise utils.CustomValidationException(
                    config.STATUS_AUTHENTICATION_FAILED,
                    config.DESC_MSG0005,
                    f"User '{user_email}' is not associated with organization '{org_name}'"
                )
        elif user_role != "SUPER ADMIN":
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                f"Invalid user role: '{user_role}'"
            )

        # Step 6: Check if module exists and is active in module_master
        query = f"""
            SELECT 1
            FROM "{config.SCHEMANAME}".module_master
            WHERE module_code = %s AND LOWER(module_status) = 'active'
        """
        cursor.execute(query, (module_code,))
        if not cursor.fetchone():
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                f"Module '{module_code}' not found or inactive"
            )
            
        # Step 7: Check org_module_master
        query = f"""
            SELECT 1
            FROM "{config.SCHEMANAME}".org_module_master
            WHERE org_name = %s AND module_code = %s AND LOWER(org_module_status) = 'active'
        """
        cursor.execute(query, (org_name, module_code))
        if not cursor.fetchone():
            raise utils.CustomValidationException(
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                f"Module '{module_code}' mapping to organization '{org_name}' not found or inactive"
            )

        # Step 8: Validate Company and Company Module (if company_id provided)
        if company_id:
            # Check company_master
            query = f"""
                SELECT 1
                FROM "{config.SCHEMANAME}".company_master
                WHERE company_id = %s AND org_name = %s AND LOWER(company_status) = 'active'
            """
            cursor.execute(query, (company_id, org_name))
            if not cursor.fetchone():
                raise utils.CustomValidationException(
                    config.STATUS_AUTHENTICATION_FAILED,
                    config.DESC_MSG0005,
                    f"Company '{company_id}' not found or inactive in organization '{org_name}'"
                )
                
            # Check company_module_master
            query = f"""
                SELECT 1
                FROM "{config.SCHEMANAME}".company_module_master
                WHERE company_id = %s AND org_name = %s AND module_code = %s AND LOWER(company_module_status) = 'active'
            """
            cursor.execute(query, (company_id, org_name, module_code))
            if not cursor.fetchone():
                raise utils.CustomValidationException(
                    config.STATUS_AUTHENTICATION_FAILED,
                    config.DESC_MSG0005,
                    f"Company '{company_id}' mapping to module '{module_code}' not found or inactive"
                )

        return config.STATUS_SUCCESS, config.DESC_MSG0007, ""

    except utils.CustomValidationException as e:
        return e.status_code, e.status_description, e.error_message

    except Exception as e:
        return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e)

    finally:
        # Step 8: Ensure DB resources are closed
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass
