"""This module provides utility functions for logging audit trails, generating API responses, connecting to a PostgreSQL database, uploading files to Azure Blob Storage, and handling file downloads."""

from cryptography.fernet import InvalidToken
from cryptography.fernet import Fernet, MultiFernet
import json
import os
import base64

import psycopg2
import requests

from common_functions import config


class CustomValidationException(Exception):
    """
    Custom exception class for validation-related errors (e.g., key, user, API).

    Attributes:
        status_code (int): The HTTP status code representing the error.
        status_description (str): A short description of the error status.
        error_message (str): The detailed error message.
    """

    def __init__(self, status_code, status_description, error_message):
        """
        Initialize the custom exception with status code, description, and message.

        Args:
            status_code (int): The status code to return in the response.
            status_description (str): A short summary of the error.
            error_message (str): A more detailed explanation of the error.
        """
        super().__init__(error_message)
        self.status_code = status_code
        self.status_description = status_description
        self.error_message = error_message


def f_log_audit_trail(
    log_type,
    request_id,
    api_name,
    user_id,
    request_timestamp,
    input_json,
    status_code,
    status_description,
    error_message,
):
    """
    Logs the audit trail of a request to the database.
    """
    # Step 1: Validate required fields
    required_fields = [log_type, request_id, api_name]
    if any(field is None for field in required_fields):
        return "ERROR"
    conn = None
    cursor = None
    try:

        # Step 3: Convert input_json to string if needed
        if isinstance(input_json, dict):
            input_json = json.dumps(input_json)

        # Step 4: Clean helper
        def clean(val):
            return str(val).replace("|", " ") if val is not None else None

        log_data = {
            "log_type": clean(log_type),
            "request_id": request_id,
            "api_name": clean(api_name),
            "user_id": clean(user_id),
            "request_timestamp": clean(request_timestamp),
            "input_json": clean(input_json),
            "status_code": clean(status_code),
            "status_description": clean(status_description),
            "error_message": clean(error_message),
        }

        insert_query = f"""
            INSERT INTO "{config.SCHEMANAME}".audit_log_bm (
                log_type, request_id, api_name, user_id, request_timestamp,
                input_json, status_code, status_description, error_message
            ) VALUES (
                %(log_type)s, %(request_id)s, %(api_name)s, %(user_id)s,
                %(request_timestamp)s, %(input_json)s, %(status_code)s,
                %(status_description)s, %(error_message)s
            )
        """

        conn = f_connect_to_db()
        if not conn:
            return "ERROR"
        cursor = conn.cursor()
        cursor.execute(insert_query, log_data)
        conn.commit()
        return "SUCCESS"

    except Exception:
        return "ERROR"
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass


def f_generate_response(
    status_code, status_description="", error_message="", response_body=None
):
    """
    Generates a standardized API response.

    Args:
        status_code (int): HTTP status code
        status_description (str, optional): Description of the status
        error_message (str, optional): Error message if any
        response_body (dict, optional): Response data

    Returns:
        dict: Standardized response
    """
    response = {
        "status_code": status_code,
        "status_description": status_description,
        "error_message": error_message,
    }

    if response_body is not None:
        response["response_body"] = response_body

    return response


def f_connect_to_db():
    """
    Establishes a connection to the PostgreSQL database using environment variables.

    Returns:
        conn: A valid connection object if successful, None otherwise.
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST_BM"),
            database=os.getenv("DB_NAME_BM"),
            user=os.getenv("DB_USER_BM"),
            password=os.getenv("DB_PASSWORD_BM"),
            port=os.getenv("DB_PORT_BM", 5432),
        )
        return conn
    except Exception:
        return None


def _check_file_size_fallback(str_blob_file_path: str, max_file_size_mb: int) -> tuple:
    """
    Fallback method using range request to get file size
    """
    try:
        # Use range request to get just the first byte and check Content-Range header
        headers = {'Range': 'bytes=0-0'}
        response = requests.get(str_blob_file_path, headers=headers, timeout=60)

        if response.status_code == 206:  # Partial Content
            content_range = response.headers.get('Content-Range')
            if content_range:
                # Content-Range format: "bytes 0-0/total_size"
                total_size = int(content_range.split('/')[-1])
                file_size_mb = round(total_size / (1024 * 1024), 2)

                if file_size_mb <= max_file_size_mb:
                    return "SUCCESS", file_size_mb
                else:
                    return "ERROR", f"File size {file_size_mb}MB exceeds limit of {max_file_size_mb}MB"

        return "ERROR", "Unable to determine file size"

    except Exception as e:
        return "ERROR", f"Fallback size check failed: {str(e)}"

def f_check_file_size(str_blob_file_path: str) -> tuple:
    """
    Checks the size of a file accessible at the provided URL efficiently
    and returns status and size in MB.

    Args:
        str_blob_file_path (str): Full URL to the blob with SAS token.

    Returns:
        tuple: ("SUCCESS" or "ERROR", size_in_MB or error_message)
    """
    try:
        if not str_blob_file_path:
            return "ERROR", "No file path provided"

        max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "25"))

        # ✅ Use HEAD request to get Content-Length without downloading file
        response = requests.head(str_blob_file_path, timeout=120)

        if response.status_code == 200:
            # Get file size from Content-Length header
            content_length = response.headers.get('Content-Length')

            if content_length:
                file_size_bytes = int(content_length)
                file_size_mb = round(file_size_bytes / (1024 * 1024), 2)

                # Check against maximum allowed size
                if file_size_mb <= max_file_size_mb:
                    return "SUCCESS", file_size_mb
                else:
                    return "ERROR", f"File size {file_size_mb}MB exceeds limit of {max_file_size_mb}MB"
            else:
                # Fallback: If Content-Length not available, use range request
                return _check_file_size_fallback(str_blob_file_path, max_file_size_mb)

        elif response.status_code == 404:
            return "ERROR", "File not found"
        elif response.status_code == 403:
            return "ERROR", "Access denied - check SAS token permissions"
        else:
            return "ERROR", f"HTTP {response.status_code}: {response.reason}"

    except requests.exceptions.Timeout:
        return "ERROR", "Request timeout"
    except requests.exceptions.RequestException as e:
        return "ERROR", f"Request failed: {str(e)}"
    except Exception as e:
        return "ERROR", f"Unexpected error: {str(e)}"


def f_connect_to_external_db(DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT, SCHEMANAME):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        # Set the schema after connection
        if SCHEMANAME:
            cursor = conn.cursor()
            cursor.execute(f'SET search_path TO "{SCHEMANAME}"')
            cursor.close()
        return conn
    except Exception:
        return None


def f_get_fernet(org_name=None):
    """
    Returns Fernet or MultiFernet instance.
    - Encrypt → uses newest key
    - Decrypt → tries all keys
    """
    keys = []

    if org_name and isinstance(org_name, str) and org_name.strip():
        clean_org = org_name.strip().replace(" ", "_").upper()
        keys.extend([
            os.getenv(f"{clean_org}_KEY_V2", ""),
            os.getenv(f"{clean_org}_KEY_V1", "")
        ])
    else:
        keys.extend([
            os.getenv("APP_KEY_V2", ""),
            os.getenv("APP_KEY_V1", "")
        ])

    keys = [k for k in keys if k]

    if not keys:
        raise CustomValidationException(
            config.STATUS_INVALID_INPUT,
            config.DESC_MSG0009,
            "No encryption keys configured"
        )

    try:
        fernets = [Fernet(k.encode()) for k in keys]
        return MultiFernet(fernets) if len(fernets) > 1 else fernets[0]
    except Exception:
        raise CustomValidationException(
            config.STATUS_SYSTEM_EXCEPTION,
            config.DESC_MSG0004,
            "Invalid Fernet key format"
        )


def f_encrypt_data(data, org_name=None, string_flag=False):
    """
    Encrypt the provided input as encrypted bytes or base64 string.

    - Accepts string, JSON, or nested JSON (dict/list). Non-strings are JSON-serialized.
    - Returns encrypted bytes directly for database storage by default.
    - If string_flag=True, returns base64 encoded string.
    - Supports MultiFernet for key rotation (encrypts with newest key).

    Args:
        data: Input data to encrypt
        org_name: Organization name for key selection
        string_flag: If True, return base64 encoded string; if False, return bytes

    Returns:
        Tuple: (encrypted_data: bytes or str, status_code: int, status_description: str, error_message: str)
    """
    try:
        # Normalize input to a string
        if isinstance(data, str):
            plaintext = data
        else:
            # Serialize any JSON-like input (dict/list/other) deterministically
            plaintext = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

        if not plaintext or not str(plaintext).strip():
            raise CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Input cannot be empty"
            )

        # Get MultiFernet or Fernet cipher (supports key rotation)
        cipher = f_get_fernet(org_name)

        # Encrypt the data (MultiFernet uses newest key automatically)
        try:
            encrypted_bytes = cipher.encrypt(plaintext.encode("utf-8"))
        except Exception as e:
            raise CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                f"Encryption failed: {str(e)}"
            )

        if string_flag:
            return encrypted_bytes.decode("utf-8"), config.STATUS_SUCCESS, config.DESC_MSG0007, ""
        else:
            return encrypted_bytes, config.STATUS_SUCCESS, config.DESC_MSG0007, ""

    except CustomValidationException as e:
        return None, e.status_code, e.status_description, e.error_message
    except Exception as e:
        return None, config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e)


def f_decrypt_data(encrypted_data, org_name=None, is_string=False, parse_json=True):
    """
    Decrypt encrypted bytes or base64 string using Fernet/MultiFernet encryption.

    - Supports MultiFernet for key rotation (tries all keys automatically).
    - If is_string=True: input is treated as base64 encoded string.
    - If is_string=False: input is raw bytes or memoryview from database.
    - If parse_json=True: attempts to parse decrypted text as JSON; returns string if parsing fails.

    Args:
        encrypted_data (bytes or str or memoryview): Encrypted data to decrypt
        org_name (str): Organization name for key selection
        is_string (bool): If True, input is base64 string; if False, input is bytes/memoryview
        parse_json (bool): If True, attempt to parse decrypted text as JSON

    Returns:
        Tuple: (decrypted_data, status_code, status_description, error_message)

    Examples:
        Input (bytes): b'gAAAAABh...'  # encrypted bytes from database
        Input (memoryview): <memory at 0x...>  # bytea from PostgreSQL
        Input (string): "Z0FBQUFBQmg..."  # base64 encoded encrypted data
        Output: {"name": "value"} or "plain text"  # decrypted and optionally parsed
    """
    try:
        # Convert input to bytes based on is_string flag
        if is_string:
            if not isinstance(encrypted_data, str) or not encrypted_data.strip():
                raise CustomValidationException(
                    config.STATUS_INVALID_INPUT,
                    config.DESC_MSG0001,
                    "Encrypted data must be a non-empty string when is_string=True"
                )
            encrypted_bytes = encrypted_data.encode("utf-8")
        else:
            if isinstance(encrypted_data, memoryview):
                encrypted_bytes = bytes(encrypted_data)
            elif isinstance(encrypted_data, bytes):
                encrypted_bytes = encrypted_data
            else:
                raise CustomValidationException(
                    config.STATUS_INVALID_INPUT,
                    config.DESC_MSG0001,
                    "Encrypted data must be bytes or memoryview"
                )

        cipher = f_get_fernet(org_name)

        try:
            decrypted_text = cipher.decrypt(encrypted_bytes).decode("utf-8")
        except InvalidToken:
            raise CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Invalid or tampered encrypted data"
            )

        if parse_json:
            try:
                restored = json.loads(decrypted_text)
                return restored, config.STATUS_SUCCESS, config.DESC_MSG0007, ""
            except json.JSONDecodeError:
                pass

        return decrypted_text, config.STATUS_SUCCESS, config.DESC_MSG0007, ""

    except CustomValidationException as e:
        return None, e.status_code, e.status_description, e.error_message
    except Exception as e:
        return None, config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e)
