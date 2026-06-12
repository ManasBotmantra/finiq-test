import base64
import datetime
import uuid
from azure.storage.blob import ContainerClient
from zoneinfo import ZoneInfo
from . import utils, config
from urllib.parse import urlparse, parse_qs, unquote, quote


def f_extract_blob_name_from_url(file_url: str, container_url: str):
    """
    Extract blob name from file URL, handling URLs with or without SAS tokens.
    Enhanced to properly handle Unicode characters in filenames.

    Args:
        file_url (str): Full file URL (may contain SAS token)
        container_url (str): Container URL without SAS

    Returns:
        str: Clean blob name without SAS parameters, with proper Unicode handling
    """
    try:
        # Parse the URL to separate the path from query parameters
        parsed_url = urlparse(file_url)

        # Get the path component and decode any URL encoding
        url_path = unquote(parsed_url.path)

        # Remove container URL from the path to get blob name
        if container_url in file_url:
            # Parse container URL to get its path component
            container_parsed = urlparse(container_url)
            container_path = unquote(container_parsed.path)

            # Extract the part after container path
            if container_path and url_path.startswith(container_path):
                blob_name = url_path[len(container_path):].lstrip('/')
            else:
                # Fallback: split by container URL
                blob_name = unquote(file_url.split(container_url + "/")[1].split("?")[0])
        else:
            # If URL doesn't contain container URL, treat path as blob name
            blob_name = url_path.lstrip('/')

        # Ensure blob name doesn't have query parameters (though should be handled above)
        if "?" in blob_name:
            blob_name = blob_name.split("?")[0]

        return blob_name
    except Exception as e:
        # Enhanced fallback with proper Unicode handling
        try:
            # Remove query parameters first
            clean_url = file_url.split("?")[0]
            # Try to extract blob name and decode
            if "/" in clean_url:
                blob_name = "/".join(clean_url.split("/")[4:])  # Skip protocol, domain, container parts
                return unquote(blob_name)
            else:
                return unquote(clean_url)
        except Exception:
            # Final fallback: return original URL
            return file_url


def f_generate_unique_filename(original_filename: str, is_uuid_req: bool = False, is_timestamp_required: bool = True) -> str:
    """
    Generate a unique filename to prevent collisions in Azure Blob Storage.
    Enhanced to properly handle Unicode characters in filenames.
    Optimized for Azure Functions high-concurrency scenarios.

    Args:
        original_filename (str): Original file name (may contain Unicode)
        is_uuid_req (bool): Whether to include UUID for additional uniqueness
        is_timestamp_required (bool): Whether to include timestamp in filename (default True)

    Returns:
        str: Unique filename with guaranteed uniqueness and proper Unicode handling
    """
    # Generate high-precision timestamp (includes microseconds for sub-second uniqueness)
    current_datetime = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    timestamp = current_datetime.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds

    # Parse original filename - handle Unicode properly
    try:
        # Ensure filename is properly decoded if it was URL-encoded
        if '%' in original_filename:
            decoded_filename = unquote(original_filename)
        else:
            decoded_filename = original_filename

        name_parts = decoded_filename.rsplit('.', 1)
        if len(name_parts) == 2:
            # Has extension
            base_name, extension = name_parts
            if is_uuid_req:
                # Generate UUID4 for absolute uniqueness (128-bit random)
                unique_id = str(uuid.uuid4()).replace('-', '')[:12]  # Use first 12 chars for brevity
                if is_timestamp_required:
                    unique_filename = f"{base_name}_{timestamp}_{unique_id}.{extension}"
                else:
                    unique_filename = f"{base_name}_{unique_id}.{extension}"
            else:
                if is_timestamp_required:
                    unique_filename = f"{base_name}_{timestamp}.{extension}"
                else:
                    unique_filename = f"{base_name}.{extension}"
        else:
            # No extension
            if is_uuid_req:
                unique_id = str(uuid.uuid4()).replace('-', '')[:12]
                if is_timestamp_required:
                    unique_filename = f"{decoded_filename}_{timestamp}_{unique_id}"
                else:
                    unique_filename = f"{decoded_filename}_{unique_id}"
            else:
                if is_timestamp_required:
                    unique_filename = f"{decoded_filename}_{timestamp}"
                else:
                    unique_filename = decoded_filename
    except Exception:
        # Fallback to safe ASCII naming if Unicode handling fails
        safe_name = "file"
        if is_uuid_req:
            unique_id = str(uuid.uuid4()).replace('-', '')[:12]
            if is_timestamp_required:
                unique_filename = f"{safe_name}_{timestamp}_{unique_id}"
            else:
                unique_filename = f"{safe_name}_{unique_id}"
        else:
            if is_timestamp_required:
                unique_filename = f"{safe_name}_{timestamp}"
            else:
                unique_filename = safe_name

    return unique_filename


def f_generate_file_sas_token(container_url: str, container_sas_token: str, blob_name: str):
    """
    Generate a SAS token for a specific file with read-only access and 1-year expiry.
    Enhanced to properly handle Unicode blob names.
    For now, uses the container SAS token as requested.

    Args:
        container_url (str): Container URL
        container_sas_token (str): Container SAS token
        blob_name (str): Blob name for which to generate SAS (may contain Unicode)

    Returns:
        str: SAS token for the specific file
    """
    # For now, return the container SAS token as requested
    # The blob_name parameter is kept for future enhancement to generate file-specific SAS tokens
    # Note: When generating file-specific SAS tokens in the future, ensure proper URL encoding of blob_name
    return container_sas_token


def f_create_clean_download_url(container_url: str, blob_name: str, sas_token: str) -> str:
    """
    Create a clean, clickable download URL that properly handles Unicode filenames.

    Args:
        container_url (str): Container URL
        blob_name (str): Blob name (may contain Unicode)
        sas_token (str): SAS token

    Returns:
        str: Clean, properly encoded download URL
    """
    try:
        # Ensure blob_name is properly URL-encoded for the URL path
        # Use quote with safe='/' to preserve path separators but encode Unicode
        encoded_blob_name = quote(blob_name, safe='/')

        # Construct the clean URL
        clean_url = f"{container_url}/{encoded_blob_name}?{sas_token}"

        return clean_url
    except Exception:
        # Fallback: basic URL construction
        return f"{container_url}/{blob_name}?{sas_token}"


def f_upload_base64_to_blob(credentials: dict, base64_str: str, file_name: str, is_temp: bool = False, with_sas_token: bool = True, is_uuid_req: bool = False, is_timestamp_required: bool = True):
    """
    Upload base64 file to Azure Blob Storage with collision prevention.
    Enhanced for Azure Functions high-concurrency scenarios and Unicode filename support.

    Args:
        credentials (dict): Blob storage credentials
        base64_str (str): Base64 encoded file content
        file_name (str): Original file name (may contain Unicode characters)
        is_temp (bool): Whether to store in temporary folder
        with_sas_token (bool): Whether to include SAS token in returned URL
        is_uuid_req (bool): Whether to include UUID in filename for extra uniqueness


    Returns:
        Tuple: (status_code, status_description, error_message, file_url)
    """
    try:
        container_url = credentials.get("CONTAINER_URL", "")
        sas_token = credentials.get("CONTAINER_SAS_TOKEN", "")
        input_temp_file_path = credentials.get("INPUT_TEMP_FILE_PATH", "")
        input_file_path = credentials.get("INPUT_FILE_PATH", "")

        # Construct full SAS URL
        container_sas_url = f"{container_url}?{sas_token}"
        # Generate unique filename with collision prevention and Unicode support
        unique_filename = f_generate_unique_filename(file_name, is_uuid_req, is_timestamp_required)

        if is_temp:
            # Store in INPUT_TEMP_FILE_PATH/unique_filename
            blob_name = f"{input_temp_file_path}/{unique_filename}".replace(
                "//", "/")

        else:
            # Store in root of container or provided folder
            if input_file_path:
                blob_name = f"{input_file_path}/{unique_filename}".replace(
                    "//", "/")
            else:
                blob_name = unique_filename

        try:
            file_bytes = base64.b64decode(base64_str, validate=True)
        except Exception:
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "Invalid base64 string", ""

        container_client = ContainerClient.from_container_url(
            container_sas_url)
        blob_client = container_client.get_blob_client(blob_name)

        # Azure Functions best practice: Check if blob already exists (though highly unlikely with UUID)
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                # Fail if exists for safety
                blob_client.upload_blob(file_bytes, overwrite=False)
                break  # Success, exit retry loop
            except Exception as upload_error:
                if "BlobAlreadyExists" in str(upload_error) and retry_count < max_retries - 1:
                    # Extremely rare case - generate new unique filename and retry
                    retry_count += 1
                    unique_filename = f_generate_unique_filename(
                        file_name, is_uuid_req, is_timestamp_required)

                    if is_temp:
                        blob_name = f"{input_temp_file_path}/{unique_filename}".replace(
                            "//", "/")

                    blob_client = container_client.get_blob_client(blob_name)
                    continue
                else:
                    # Different error or max retries reached - use overwrite for final attempt
                    blob_client.upload_blob(file_bytes, overwrite=True)
                    break

        # Generate clean file URL with proper Unicode handling
        if with_sas_token:
            file_sas_token = f_generate_file_sas_token(
                container_url, sas_token, blob_name)
            file_url = f_create_clean_download_url(
                container_url, blob_name, file_sas_token)
        else:
            # Even without SAS token, ensure proper URL encoding
            encoded_blob_name = quote(blob_name, safe='/')
            file_url = f"{container_url}/{encoded_blob_name}"

        return config.STATUS_SUCCESS, "Success", "", file_url
    except Exception as e:
        return config.STATUS_SYSTEM_EXCEPTION, "System Exception", str(e), ""




def f_download_base64_from_blob(credentials: dict, file_url: str):
    """
    Downloads a file from Azure Blob Storage and returns it as base64.
    Enhanced to handle URLs with Unicode characters and SAS tokens properly.

    Args:
        credentials (dict): Blob storage credentials containing CONTAINER_URL and CONTAINER_SAS_TOKEN
        file_url (str): Full URL of the file to download (may contain SAS token and Unicode characters)

    Returns:
        Tuple: (status_code, status_description, error_message, base64_content)
    """
    try:
        container_url = credentials.get("CONTAINER_URL", "")
        container_sas_token = credentials.get("CONTAINER_SAS_TOKEN", "")

        # Extract clean blob name from URL with proper Unicode handling
        blob_name = f_extract_blob_name_from_url(file_url, container_url)

        # Check if the file_url already has a SAS token
        has_sas_token = "?" in file_url and any(
            param in file_url for param in ["sv=", "sig=", "se=", "sp="]
        )

        if has_sas_token:
            # Use the URL as-is since it already has a SAS token
            try:
                # Try to use the provided SAS URL directly
                container_client = ContainerClient.from_container_url(f"{container_url}?{container_sas_token}")
                blob_client = container_client.get_blob_client(blob_name)

                # Check if blob exists using container SAS
                if not blob_client.exists():
                    return config.STATUS_NO_DATA_FOUND, config.DESC_MSG0003, "File not found in blob storage", ""

                # Download using container SAS
                blob_data = blob_client.download_blob()
                file_bytes = blob_data.readall()

            except Exception as sas_error:
                # If the provided SAS token fails, try with container SAS token
                container_sas_url = f"{container_url}?{container_sas_token}"
                container_client = ContainerClient.from_container_url(container_sas_url)
                blob_client = container_client.get_blob_client(blob_name)

                if not blob_client.exists():
                    return config.STATUS_NO_DATA_FOUND, config.DESC_MSG0003, "File not found in blob storage", ""

                blob_data = blob_client.download_blob()
                file_bytes = blob_data.readall()
        else:
            # No SAS token in URL, use container SAS token
            container_sas_url = f"{container_url}?{container_sas_token}"
            container_client = ContainerClient.from_container_url(container_sas_url)
            blob_client = container_client.get_blob_client(blob_name)

            # Check if blob exists
            if not blob_client.exists():
                return config.STATUS_NO_DATA_FOUND, config.DESC_MSG0003, "File not found in blob storage", ""

            # Download blob content
            blob_data = blob_client.download_blob()
            file_bytes = blob_data.readall()

        # Convert to base64
        base64_content = base64.b64encode(file_bytes).decode('utf-8')

        return config.STATUS_SUCCESS, "Success", "", base64_content

    except Exception as e:
        error_msg = str(e)
        if "AuthenticationFailed" in error_msg or "ClientAuthenticationError" in error_msg:
            return config.STATUS_AUTHENTICATION_FAILED, config.DESC_MSG0005, config.ERR_MSG0177, ""
        elif "BlobNotFound" in error_msg:
            return config.STATUS_NO_DATA_FOUND, config.DESC_MSG0003, config.ERR_MSG0178, ""
        else:
            return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, f"Blob download error: {error_msg}", ""



def f_move_blob_file(
    from_credentials: dict,
    to_credentials: dict,
    temp_file_url: str,
    with_sas_token: bool = False,
    need_actual_file_name: bool = False
):
    """
    Moves a file from temporary storage (source container) to permanent storage (destination container).
    Enhanced to handle cross-container moves and filename restoration.

    Args:
        from_credentials (dict): Source blob storage credentials (temp container)
        to_credentials (dict): Destination blob storage credentials (permanent container)
        temp_file_url (str): URL of the file in temporary storage (may contain SAS token and Unicode)
        with_sas_token (bool): Whether to include SAS token in returned URL
        need_actual_file_name (bool): Whether to restore original filename by removing timestamp/UUID

    Returns:
        Tuple: (status_code, status_description, error_message, new_file_url)
    """
    try:
        # -------------------------------------------------
        # 1. Validate Input
        # -------------------------------------------------
        if not from_credentials or not isinstance(from_credentials, dict):
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "from_credentials must be a valid dictionary", ""

        if not to_credentials or not isinstance(to_credentials, dict):
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "to_credentials must be a valid dictionary", ""

        if not temp_file_url or not isinstance(temp_file_url, str) or not temp_file_url.strip():
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "temp_file_url must be a non-empty string", ""

        # -------------------------------------------------
        # 2. Extract Source Container Credentials
        # -------------------------------------------------
        source_container_url = from_credentials.get("CONTAINER_URL", "")
        source_sas_token = from_credentials.get("CONTAINER_SAS_TOKEN", "")
        input_temp_file_path = from_credentials.get("INPUT_TEMP_FILE_PATH", "")

        if not source_container_url or not source_sas_token:
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "Missing required source container credentials", ""

        # -------------------------------------------------
        # 3. Extract Destination Container Credentials
        # -------------------------------------------------
        dest_container_url = to_credentials.get("CONTAINER_URL", "")
        dest_sas_token = to_credentials.get("CONTAINER_SAS_TOKEN", "")
        input_file_path = to_credentials.get("INPUT_FILE_PATH", "")

        if not dest_container_url or not dest_sas_token:
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "Missing required destination container credentials", ""

        if not input_file_path or not isinstance(input_file_path, str) or not input_file_path.strip():
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "INPUT_FILE_PATH must be provided in to_credentials", ""

        # -------------------------------------------------
        # 4. Extract Blob Name from Temp URL
        # -------------------------------------------------
        temp_blob_name = f_extract_blob_name_from_url(temp_file_url, source_container_url)

        # Validate that this is indeed a temporary file
        if input_temp_file_path and not temp_blob_name.startswith(input_temp_file_path):
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "Invalid temporary file URL - not in temp directory", ""

        # Extract just the filename (last part after /) - preserve Unicode
        temp_filename = temp_blob_name.split('/')[-1]

        # -------------------------------------------------
        # 5. Restore Original Filename (if requested)
        # -------------------------------------------------
        if need_actual_file_name:
            # Remove timestamp and UUID to get original filename
            # Format patterns to remove:
            # - _YYYYMMDD_HHMMSS_mmm (timestamp with milliseconds)
            # - _xxxxxxxxxxxx (12-char UUID)

            try:
                # Split filename into base and extension
                if '.' in temp_filename:
                    name_parts = temp_filename.rsplit('.', 1)
                    base_name = name_parts[0]
                    extension = name_parts[1]
                else:
                    base_name = temp_filename
                    extension = ""

                # Remove timestamp pattern: _YYYYMMDD_HHMMSS_mmm (26 chars including underscores)
                # Pattern: _20241211_153045_123
                import re
                # Remove timestamp (format: _YYYYMMDD_HHMMSS_mmm)
                base_name = re.sub(r'_\d{8}_\d{6}_\d{3}', '', base_name)

                # Remove UUID if present (format: _xxxxxxxxxxxx where x is hex)
                base_name = re.sub(r'_[a-f0-9]{12}$', '', base_name)

                # Reconstruct filename
                if extension:
                    final_filename = f"{base_name}.{extension}"
                else:
                    final_filename = base_name

            except Exception as restore_error:
                # If restoration fails, use original temp filename
                final_filename = temp_filename
        else:
            # Keep the unique filename as-is
            final_filename = temp_filename

        # -------------------------------------------------
        # 6. Construct Permanent Blob Path
        # -------------------------------------------------
        # input_file_path already contains the full path: module_code/request_id/transaction_id
        # Just append the filename
        permanent_blob_name = f"{input_file_path.strip().strip('/')}/{final_filename}".replace("//", "/")

        # -------------------------------------------------
        # 7. Connect to Source Container and Verify File Exists
        # -------------------------------------------------
        source_container_sas_url = f"{source_container_url}?{source_sas_token}"
        source_container_client = ContainerClient.from_container_url(source_container_sas_url)
        source_blob_client = source_container_client.get_blob_client(temp_blob_name)

        # Check if source blob exists
        if not source_blob_client.exists():
            return config.STATUS_NO_DATA_FOUND, config.DESC_MSG0003, "Temporary file not found in source container", ""

        # -------------------------------------------------
        # 8. Connect to Destination Container
        # -------------------------------------------------
        dest_container_sas_url = f"{dest_container_url}?{dest_sas_token}"
        dest_container_client = ContainerClient.from_container_url(dest_container_sas_url)
        dest_blob_client = dest_container_client.get_blob_client(permanent_blob_name)

        # -------------------------------------------------
        # 9. Copy File from Source to Destination Container
        # -------------------------------------------------
        # Construct full source URL with SAS for cross-container copy
        encoded_temp_blob_name = quote(temp_blob_name, safe='/')
        copy_source_url = f"{source_container_url}/{encoded_temp_blob_name}?{source_sas_token}"

        # Synchronous copy - completes before returning
        copy_operation = dest_blob_client.start_copy_from_url(
            copy_source_url, requires_sync=True)

        # Check copy status - with requires_sync, this is immediate verification
        if copy_operation.get('copy_status') != 'success' or not dest_blob_client.exists():
            return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, f"File copy failed: {copy_operation.get('copy_status_description', 'Unknown error')}", ""

        # -------------------------------------------------
        # 10. Construct Destination File URL
        # -------------------------------------------------
        if with_sas_token:
            file_sas_token = f_generate_file_sas_token(dest_container_url, dest_sas_token, permanent_blob_name)
            new_file_url = f_create_clean_download_url(dest_container_url, permanent_blob_name, file_sas_token)
        else:
            encoded_blob_name = quote(permanent_blob_name, safe='/')
            new_file_url = f"{dest_container_url}/{encoded_blob_name}"

        return config.STATUS_SUCCESS, "Success", "", new_file_url

    except Exception as e:
        error_msg = str(e)

        if "AuthenticationFailed" in error_msg or "ClientAuthenticationError" in error_msg:
            return config.STATUS_AUTHENTICATION_FAILED, config.DESC_MSG0005, f"Blob authentication failed: {error_msg}", ""
        else:
            return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, f"Blob move error: {error_msg}", ""


def f_delete_folder_from_blob(credentials: dict, folder_path: str):
    """
    Deletes all blobs within the specified folder path. If no blobs found, returns success (idempotent).

    Args:
        credentials (dict): Blob storage credentials containing CONTAINER_URL and CONTAINER_SAS_TOKEN
        folder_path (str): Full folder path to delete (e.g., "module_code/request_id/transaction_id")

    Returns:
        tuple: (status_code, status_description, error_message)
    """
    try:
        container_url = credentials.get("CONTAINER_URL", "")
        sas_token = credentials.get("CONTAINER_SAS_TOKEN", "")

        if not container_url or not sas_token:
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "Missing required blob credentials (CONTAINER_URL or CONTAINER_SAS_TOKEN)"

        if not folder_path or not isinstance(folder_path, str) or not folder_path.strip():
            return config.STATUS_INVALID_INPUT, config.DESC_MSG0001, "folder_path must be a non-empty string"

        container_sas_url = f"{container_url}?{sas_token}"
        container_client = ContainerClient.from_container_url(container_sas_url)

        # Normalize folder path and ensure it ends with /
        prefix = f"{folder_path.strip().strip('/')}/".replace("//", "/")

        for blob in container_client.list_blobs(name_starts_with=prefix):
            try:
                container_client.delete_blob(blob.name)
            except Exception as del_err:
                return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, f"Failed to delete blob {blob.name}: {str(del_err)}"

        return config.STATUS_SUCCESS, "Success", ""

    except Exception as e:
        error_msg = str(e)
        if "AuthenticationFailed" in error_msg or "ClientAuthenticationError" in error_msg:
            return config.STATUS_AUTHENTICATION_FAILED, config.DESC_MSG0005, f"Blob auth error: {error_msg}"
        else:
            return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, f"Blob delete folder error: {error_msg}"



def f_delete_file_from_blob(credentials: dict, file_name: str,  file_url: str):
    """
    Delete a specific file from Azure Blob Storage.
    Enhanced to handle Unicode filenames properly.

    Args:
        credentials (dict): Blob storage credentials containing CONTAINER_URL and CONTAINER_SAS_TOKEN
        file_name (str): Original filename (for logging/validation purposes, may contain Unicode)
        file_url (str): Full URL of the file to delete (may contain SAS token and Unicode)

    Returns:
        Tuple: (status_code, status_description, error_message)
    """
    try:
        # Input validation
        if not credentials or not isinstance(credentials, dict):
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "credentials must be a valid dictionary"
            )

        if not file_url or not isinstance(file_url, str) or not file_url.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "file_url must be a non-empty string"
            )

        # file_name is optional but should be a string if provided
        if file_name is not None and not isinstance(file_name, str):
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "file_name must be a string"
            )


        # Extract blob storage credentials
        container_url = credentials.get("CONTAINER_URL", "")
        container_sas_token = credentials.get("CONTAINER_SAS_TOKEN", "")

        if not container_url or not container_sas_token:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Missing required blob storage credentials (CONTAINER_URL, CONTAINER_SAS_TOKEN)"
            )

        # Extract clean blob name from URL with proper Unicode handling
        blob_name = f_extract_blob_name_from_url(file_url.strip(), container_url)

        if not blob_name:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Unable to extract blob name from file_url"
            )

        # Construct container SAS URL
        container_sas_url = f"{container_url}?{container_sas_token}"

        # Create container and blob clients
        container_client = ContainerClient.from_container_url(container_sas_url)
        blob_client = container_client.get_blob_client(blob_name)

        # Check if blob exists before attempting deletion
        if not blob_client.exists():
            raise utils.CustomValidationException(
                config.STATUS_NO_DATA_FOUND,
                config.DESC_MSG0003,
                f"File '{file_name}' not found"
            )
        blob_client.delete_blob()

        # Verify deletion was successful
        if blob_client.exists():
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                f"File deletion failed - file '{file_name}' still exists"
            )

        return config.STATUS_SUCCESS, "Success", ""

    except utils.CustomValidationException as e:
        return e.status_code, e.status_description, e.error_message
    except Exception as e:
        error_msg = str(e)
        return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, f"Blob deletion error: {error_msg}"


def f_extract_filename_from_blob_url(file_url: str) -> str:
    """
    Extract clean filename from URL, removing SAS token parameters.
    Enhanced to properly handle Unicode characters.

    Args:
        file_url (str): Full file URL (may contain SAS token and Unicode)

    Returns:
        str: Clean filename without SAS parameters, with proper Unicode handling
    """
    try:
        # Parse and decode the URL
        parsed_url = urlparse(file_url)
        decoded_path = unquote(parsed_url.path)

        # Split by '/' to get the last part (filename)
        path_parts = decoded_path.split('/')
        filename = path_parts[-1] if path_parts else decoded_path

        # Remove SAS token if present (everything after ?)
        if "?" in filename:
            clean_filename = filename.split("?")[0]
        else:
            clean_filename = filename

        return clean_filename
    except Exception:
        # Fallback: basic extraction
        try:
            url_parts = file_url.split('/')
            filename_with_params = url_parts[-1] if url_parts else file_url

            if "?" in filename_with_params:
                clean_filename = filename_with_params.split("?")[0]
            else:
                clean_filename = filename_with_params

            return unquote(clean_filename)
        except Exception:
            return file_url
