import requests
import time
import json
import uuid
import logging
import datetime
from zoneinfo import ZoneInfo
from urllib.parse import quote  # Add this import
from common_functions import utils, config
import base64
from common_functions import blob_utils
from azure.storage.blob import ContainerClient
# Token cache to avoid unnecessary refreshes
_token_cache = {}


def get_access_token(tenant_id, client_id, client_secret, force_refresh=False):
    """Get Microsoft Graph access token for SharePoint operations with caching."""
    try:
        # Validate input parameters
        if not tenant_id or not client_id or not client_secret:
            raise ValueError("tenant_id, client_id, and client_secret are required")

        # Create cache key
        cache_key = f"{tenant_id}_{client_id}"

        # Check cache first (unless force refresh)
        if not force_refresh and cache_key in _token_cache:
            cached_token, cached_time = _token_cache[cache_key]
            # Check if token is still valid (refresh 5 minutes before expiry)
            if time.time() - cached_time < 3300:  # 55 minutes (tokens expire in 1 hour)
                return cached_token

        # Get new token
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }

        r = requests.post(token_url, data=payload)

        if r.status_code != config.STATUS_SUCCESS:
            r.raise_for_status()

        response_json = r.json()
        if "access_token" not in response_json:
            raise ValueError("Access token not found in authentication response")

        access_token = response_json["access_token"]
        if not access_token:
            raise ValueError("Access token is empty")

        # Cache the token
        _token_cache[cache_key] = (access_token, time.time())

        return access_token

    except Exception as e:
        raise Exception(f"Failed to get access token: {str(e)}")


def make_sharepoint_request_with_retry(credentials, request_func, max_retries=2):
    """
    Makes a SharePoint request with automatic token refresh on 401 errors.

    Args:
        credentials: SharePoint credentials containing authentication details
        request_func: Function that takes (token, site_id, drive_id) and makes the request
        max_retries: Maximum number of retry attempts (default: 2)

    Returns:
        Response object from the successful request
    """
    # Extract authentication credentials
    auth = credentials["authentication"]
    tenant_id = auth["tenant_id"]
    client_id = auth["client_id"]
    client_secret = auth["client_secret"]

    site_hostname = credentials["sharepoint"]["site_hostname"]
    site_path = credentials["sharepoint"]["site_path"]
    drive_name = credentials["sharepoint"]["drive_name"]

    # Get initial SharePoint access
    token = get_access_token(tenant_id, client_id, client_secret)
    site_id = get_site_id(token, site_hostname, site_path)
    drive_id = get_drive_id(token, site_id, drive_name)

    # Try request with automatic token refresh on 401 error
    for attempt in range(max_retries):
        try:
            response = request_func(token, site_id, drive_id)
            response.raise_for_status()

            # If successful, return the response
            return response

        except requests.exceptions.HTTPError as e:
            if (
                e.response.status_code == config.STATUS_AUTHENTICATION_FAILED
                and attempt < max_retries - 1
            ):
                # Token expired, refresh it and retry
                logging.warning(
                    f"SharePoint token expired, refreshing... (attempt {attempt + 1})"
                )
                token = get_access_token(
                    tenant_id, client_id, client_secret, force_refresh=True
                )
                continue
            else:
                # Re-raise the exception if it's not a 401 or we've exhausted retries
                raise

    # This should never be reached, but just in case
    raise Exception("Failed to make SharePoint request after all retries")


def get_site_id(token, site_hostname, site_path):
    """Get SharePoint site ID from hostname and path."""
    url = f"https://graph.microsoft.com/v1.0/sites/{site_hostname}:{site_path}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()["id"]


def get_drive_id(token, site_id, drive_name):
    """Get SharePoint drive ID from site ID and drive name."""
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    drives = r.json()["value"]
    for d in drives:
        if d["name"].lower() == drive_name.lower():
            return d["id"]
    return drives[0]["id"]


def create_folder_if_not_exists(token, drive_id, folder_path):
    """
    Creates a folder if it doesn't exist in SharePoint drive.
    Returns the folder ID.
    """
    try:
        # Check if folder exists - URL encode the path
        encoded_path = quote(folder_path, safe="/")
        check_url = (
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}"
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(check_url, headers=headers)

        if response.status_code == config.STATUS_SUCCESS:
            # Folder exists, return its ID
            return response.json()["id"]

        # Folder doesn't exist, create it
        create_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children"
        folder_data = {
            "name": folder_path.split("/")[-1],
            "folder": {},
            "@microsoft.graph.conflictBehavior": "replace",
        }

        # If folder_path has parent directories, create them first
        if "/" in folder_path:
            parent_path = "/".join(folder_path.split("/")[:-1])
            parent_id = create_folder_if_not_exists(token, drive_id, parent_path)
            create_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{parent_id}/children"

        response = requests.post(create_url, headers=headers, json=folder_data)

        # If creation fails due to conflict, try to get the existing folder
        if (
            response.status_code == config.STATUS_DUPLICATE_DATA
        ):  # Conflict - folder already exists
            check_response = requests.get(check_url, headers=headers)
            if check_response.status_code == config.STATUS_SUCCESS:
                return check_response.json()["id"]

        response.raise_for_status()
        return response.json()["id"]

    except Exception as e:
        raise Exception(f"Failed to create folder {folder_path}: {str(e)}")


def _generate_collision_proof_filename(original_filename: str) -> str:
    """
    Generate a globally unique filename to prevent collisions in SharePoint.
    Optimized for Azure Functions high-concurrency scenarios.

    Args:
        original_filename (str): Original file name

    Returns:
        str: Unique filename with guaranteed uniqueness
    """
    # Generate high-precision timestamp (includes microseconds for sub-second uniqueness)
    current_datetime = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    timestamp = current_datetime.strftime("%Y%m%d_%H%M%S_%f")[
        :-3
    ]  # Include milliseconds

    # Generate UUID4 for absolute uniqueness (128-bit random)
    unique_id = str(uuid.uuid4()).replace("-", "")[
        :12
    ]  # Use first 12 chars for brevity

    # Parse original filename
    name_parts = original_filename.rsplit(".", 1)
    if len(name_parts) == 2:
        # Has extension
        base_name, extension = name_parts
        # Create collision-proof filename: basename_timestamp_uuid.extension
        unique_filename = f"{base_name}_{timestamp}_{unique_id}.{extension}"
    else:
        # No extension
        unique_filename = f"{original_filename}_{timestamp}_{unique_id}"

    return unique_filename


def get_anonymous_share_link(token, drive_id, file_id):
    """
    Creates an anonymous (public) view link for a file in SharePoint.
    Returns the shareable link URL or empty string on failure.
    """
    try:
        # Try different payload configurations for creating share links
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}/createLink"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payloads = [
            {"type": "view", "scope": "anonymous"},
            {"type": "view", "scope": "organization"},
            {"type": "view", "scope": "users"},
            {"type": "view"},  # Default scope
        ]

        for payload in payloads:
            try:
                logging.warning(f"Trying share link payload: {payload}")
                resp = requests.post(url, headers=headers, json=payload)
                resp.raise_for_status()

                response_data = resp.json()
                logging.warning(f"Share link response: {response_data}")

                # Extract shareable link from response
                shareable_link = ""
                if "webUrl" in response_data:
                    shareable_link = response_data["webUrl"]
                elif "url" in response_data:
                    shareable_link = response_data["url"]
                elif "link" in response_data:
                    link_data = response_data["link"]
                    shareable_link = link_data.get("webUrl") or link_data.get("url")

                # Verify that the link looks like a shareable link
                if shareable_link and (
                    ":b:/g/" in shareable_link or "?e=" in shareable_link
                ):
                    logging.warning(f"Generated shareable link: {shareable_link}")
                    return shareable_link

            except Exception as e:
                logging.warning(f"Share link method failed with payload {payload}: {str(e)}")
                continue

        # If all methods fail, try to get webUrl as fallback
        logging.warning("All share link methods failed, trying webUrl fallback...")
        file_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}"
        file_resp = requests.get(file_url, headers={"Authorization": f"Bearer {token}"})
        if file_resp.status_code == config.STATUS_SUCCESS:
            file_data = file_resp.json()
            web_url = file_data.get("webUrl", "")
            if web_url:
                logging.warning(f"Using webUrl fallback: {web_url}")
                return web_url

        logging.warning("All methods failed to create shareable link")
        return ""

    except Exception as e:
        logging.warning(f"Error creating share link: {str(e)}")
        return ""


def get_file_metadata(token, drive_id, file_path):
    """
    Gets file metadata from SharePoint.
    Returns dict with file_name, file_url, file_type.
    """
    try:
        # URL encode the path to handle non-ASCII characters
        encoded_path = quote(file_path, safe="/")
        file_url = (
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}"
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(file_url, headers=headers)
        response.raise_for_status()

        file_data = response.json()
        return {
            "file_name": file_data.get("name", ""),
            "file_url": file_data.get("@microsoft.graph.downloadUrl", ""),
            "file_type": file_data.get("file", {}).get("mimeType", ""),
        }
    except Exception as e:
        raise Exception(f"Failed to get file metadata for {file_path}: {str(e)}")


def f_generate_permanent_sharepoint_url(credentials: dict, graph_api_url: str):
    """
    Generates a permanent SharePoint URL that can be accessed directly in browser without authentication.
    Creates an anonymous share link that doesn't require login and doesn't expire.
    This solves the issue of expired download URLs stored in the database.

    Args:
        credentials: SharePoint credentials
        graph_api_url: Graph API URL (e.g., https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id})

    Returns:
        (status_code, status_description, error_message, anonymous_share_url)
    """
    try:
        # Extract authentication credentials
        auth = credentials["authentication"]
        tenant_id = auth["tenant_id"]
        client_id = auth["client_id"]
        client_secret = auth["client_secret"]

        # Get fresh access token
        token = get_access_token(tenant_id, client_id, client_secret)

        # Get file metadata to get webUrl
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(graph_api_url, headers=headers)

        if response.status_code != config.STATUS_SUCCESS:
            return (
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                f"Failed to get file metadata: {response.text}",
                "",
            )

        file_data = response.json()
        file_id = file_data.get("id", "")

        if not file_id:
            return (
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                "No file ID found in file metadata",
                "",
            )

        # Extract drive_id from the graph_api_url
        if "/drives/" in graph_api_url:
            drive_id = graph_api_url.split("/drives/")[1].split("/")[0]
        else:
            return (
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                "Could not extract drive ID from URL",
                "",
            )

        # Create anonymous share link
        anonymous_link = get_anonymous_share_link(token, drive_id, file_id)
        if anonymous_link:
            return config.STATUS_SUCCESS, "Success", "", anonymous_link

        # Fallback to webUrl if anonymous link creation fails
        web_url = file_data.get("webUrl", "")
        if web_url:
            return config.STATUS_SUCCESS, "Success", "", web_url

        return (
            config.STATUS_SYSTEM_EXCEPTION,
            config.DESC_MSG0004,
            "Could not generate shareable link",
            "",
        )

    except Exception as e:
        return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e), ""


def f_create_uuid_folder(org_name, bot_name, bot_category):
    """
    Creates a UUID folder inside the attachment_folder from bot_config SharePoint credentials
    and returns:
    - uuid_folder
    - permanent shareable folder link
    - folder_path (with / separators)

    Returns:
        (status_code, status_description, error_message, uuid_folder, folder_link, folder_path)
    """
    conn = None
    cursor = None

    try:
        if not org_name or not bot_name or not bot_category:
            return (
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "org_name, bot_name, bot_category are required",
                "",
                "",
                ""
            )

        conn = utils.f_connect_to_db()
        cursor = conn.cursor()

        cursor.execute(
            f"""
            SELECT bot_file_cred_json
            FROM "{config.SCHEMANAME}".bot_config
            WHERE LOWER(org_name) = %s AND LOWER(bot_name) = %s AND LOWER(bot_category) = %s
            """,
            (org_name.lower(), bot_name.lower(), bot_category.lower()),
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return (
                config.STATUS_NO_DATA_FOUND,
                config.DESC_MSG0003,
                "bot_file_cred_json not found",
                "",
                "",
                ""
            )

        storage_credentials = row[0]

        # Extract JSON credentials
        auth = storage_credentials["authentication"]
        sp = storage_credentials["sharepoint"]
        attachment_folder = storage_credentials["file_config"]["attachment_folder"].rstrip("/")

        # Generate UUID
        uuid_folder = str(uuid.uuid4())

        # Final folder structure
        folder_path = f"{attachment_folder}/{uuid_folder}"

        # Authenticate
        token = get_access_token(auth["tenant_id"], auth["client_id"], auth["client_secret"])
        site_id = get_site_id(token, sp["site_hostname"], sp["site_path"])
        drive_id = get_drive_id(token, site_id, sp["drive_name"])

        # Create folder
        folder_id = create_folder_if_not_exists(token, drive_id, folder_path)

        # Generate shareable link
        graph_api_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}"
        status, desc, err, folder_link = f_generate_permanent_sharepoint_url(storage_credentials, graph_api_url)

        if status != config.STATUS_SUCCESS:
            return status, desc, err, "", "", ""

        return (
            config.STATUS_SUCCESS,
            config.DESC_MSG0007,
            "",
            uuid_folder,
            folder_link,
            folder_path
        )

    except Exception as e:
        return (
            config.STATUS_SYSTEM_EXCEPTION,
            config.DESC_MSG0004,
            str(e),
            "",
            "",
            ""
        )

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def f_upload_base64_to_sharepoint(credentials: dict, base64_str: str, file_name: str, folder_path: str):
    """
    Uploads a file (from base64 string) directly to a specified SharePoint folder path with collision prevention.
    Enhanced for Azure Functions high-concurrency scenarios.

    Args:
        credentials (dict): SharePoint credentials containing authentication details
        base64_str (str): Base64 encoded file content
        file_name (str): Original file name
        folder_path (str): Target folder path where the file should be uploaded

    Returns:
        Tuple: (status_code, status_description, error_message, file_url, file_name)
    """
    try:
        # Extract authentication credentials from nested structure
        auth = credentials["authentication"]
        tenant_id = auth["tenant_id"]
        client_id = auth["client_id"]
        client_secret = auth["client_secret"]

        site_hostname = credentials["sharepoint"]["site_hostname"]
        site_path = credentials["sharepoint"]["site_path"]
        drive_name = credentials["sharepoint"]["drive_name"]

        token = get_access_token(tenant_id, client_id, client_secret)
        site_id = get_site_id(token, site_hostname, site_path)
        drive_id = get_drive_id(token, site_id, drive_name)

        # Create target folder if it doesn't exist
        create_folder_if_not_exists(token, drive_id, folder_path)

        # Use the original file_name directly
        upload_path = f"{folder_path}/{file_name}"

        # Decode base64
        file_bytes = base64.b64decode(base64_str)

        # Upload to target folder with original filename
        headers_auth = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/pdf"
                    }
        # URL encode the path to handle non-ASCII characters properly
        encoded_upload_path = quote(upload_path, safe='/')
        upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_upload_path}:/content"

        # Azure Functions best practice: Retry logic for SharePoint API reliability
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                r = requests.put(upload_url, headers=headers_auth, data=file_bytes)
                r.raise_for_status()
                break  # Success, exit retry loop
            except Exception as upload_error:
                if "Conflict" in str(upload_error) and retry_count < max_retries - 1:
                    # Retry with same filename
                    retry_count += 1
                    continue
                else:
                    # Different error or max retries reached
                    raise upload_error

        # Get file metadata to construct Graph API URL
        file_metadata_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_upload_path}"
        file_response = requests.get(file_metadata_url, headers=headers_auth)
        file_response.raise_for_status()

        file_data = file_response.json()
        file_id = file_data.get("id", "")

        if not file_id:
            raise Exception("Failed to get file ID after upload")

        # Construct Graph API URL for the uploaded file
        graph_api_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}"

        # Generate permanent shareable URL using f_generate_permanent_sharepoint_url
        url_status, url_desc, url_error, final_file_url = f_generate_permanent_sharepoint_url(
            credentials, graph_api_url
        )

        if url_status != config.STATUS_SUCCESS:
            # If permanent URL generation fails, fall back to the temporary download URL
            final_file_url = file_data.get("@microsoft.graph.downloadUrl", "")

        return config.STATUS_SUCCESS, "Success", "", final_file_url, file_name

    except Exception as e:
        return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e), "", ""

def f_download_file_from_blob(credentials: dict, file_url: str):
    """
    Downloads a file from Azure Blob Storage and returns raw file bytes
    along with the original filename. Deletes the blob file after successful download.

    Args:
        credentials (dict): Blob storage credentials containing
                            CONTAINER_URL and CONTAINER_SAS_TOKEN
        file_url (str): Full blob URL of the file (may contain SAS token)

    Returns:
        Tuple:
            (
                status_code,
                status_description,
                error_message,
                file_bytes,
                file_name
            )
    """
    blob_client = None
    try:
        # -------------------------------
        # 1. Validate input
        # -------------------------------
        if not credentials or not isinstance(credentials, dict):
            return (
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "credentials must be a valid dictionary",
                b"",
                ""
            )

        if not file_url or not isinstance(file_url, str) or not file_url.strip():
            return (
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "file_url must be a non-empty string",
                b"",
                ""
            )

        container_url = credentials.get("CONTAINER_URL", "")
        container_sas_token = credentials.get("CONTAINER_SAS_TOKEN", "")

        if not container_url or not container_sas_token:
            return (
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Missing required blob credentials (CONTAINER_URL, CONTAINER_SAS_TOKEN)",
                b"",
                ""
            )

        # -------------------------------
        # 2. Extract blob name & filename
        # -------------------------------
        blob_name = blob_utils.f_extract_blob_name_from_url(file_url.strip(), container_url)
        file_name = blob_utils.f_extract_filename_from_blob_url(file_url.strip())

        if not blob_name:
            return (
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "Unable to extract blob name from file_url",
                b"",
                ""
            )

        # -------------------------------
        # 3. Connect to blob container
        # -------------------------------
        container_sas_url = f"{container_url}?{container_sas_token}"
        container_client = ContainerClient.from_container_url(container_sas_url)
        blob_client = container_client.get_blob_client(blob_name)

        # -------------------------------
        # 4. Check existence
        # -------------------------------
        if not blob_client.exists():
            return (
                config.STATUS_NO_DATA_FOUND,
                config.DESC_MSG0003,
                "File not found in blob storage",
                b"",
                ""
            )

        # -------------------------------
        # 5. Download file bytes
        # -------------------------------
        blob_data = blob_client.download_blob()
        file_bytes = blob_data.readall()

        if not file_bytes:
            return (
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                "Downloaded file is empty",
                b"",
                ""
            )

        return (
            config.STATUS_SUCCESS,
            "Success",
            "",
            file_bytes,
            file_name
        )

    except Exception as e:
        error_msg = str(e)

        if "AuthenticationFailed" in error_msg or "ClientAuthenticationError" in error_msg:
            return (
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                f"Blob authentication failed: {error_msg}",
                b"",
                ""
            )
        elif "BlobNotFound" in error_msg:
            return (
                config.STATUS_NO_DATA_FOUND,
                config.DESC_MSG0003,
                "File not found in blob storage",
                b"",
                ""
            )
        else:
            return (
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                f"Blob download error: {error_msg}",
                b"",
                ""
            )


def f_upload_bytes_to_sharepoint(
    credentials: dict,
    file_bytes: bytes,
    file_name: str,
    folder_path: str
):
    try:
        auth = credentials["authentication"]
        token = get_access_token(
            auth["tenant_id"],
            auth["client_id"],
            auth["client_secret"]
        )

        sp = credentials["sharepoint"]
        site_id = get_site_id(token, sp["site_hostname"], sp["site_path"])
        drive_id = get_drive_id(token, site_id, sp["drive_name"])

        create_folder_if_not_exists(token, drive_id, folder_path)

        encoded_path = quote(f"{folder_path}/{file_name}", safe="/")
        upload_url = (
            f"https://graph.microsoft.com/v1.0/"
            f"drives/{drive_id}/root:/{encoded_path}:/content"
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/pdf"
        }

        r = requests.put(upload_url, headers=headers, data=file_bytes)
        r.raise_for_status()

        file_data = r.json()
        # Prefer a permanent link (shareable/webUrl) over expiring downloadUrl
        file_id = file_data.get("id")
        graph_api_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}" if file_id else ""

        final_url = ""
        if graph_api_url:
            url_status, url_desc, url_error, share_url = f_generate_permanent_sharepoint_url(
                credentials,
                graph_api_url
            )
            if url_status == config.STATUS_SUCCESS and share_url:
                final_url = share_url
            else:
                # Fallback to downloadUrl if permanent URL generation fails
                final_url = file_data.get("@microsoft.graph.downloadUrl", "")
        else:
            final_url = file_data.get("@microsoft.graph.downloadUrl", "")

        return config.STATUS_SUCCESS, "Success", "", final_url, file_name

    except Exception as e:
        return config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e), "", ""


def f_download_base64_from_sharepoint(credentials: dict, file_path: str):
    """
    Downloads a file from SharePoint and returns it as base64 string.

    Args:
        credentials (dict): SharePoint credentials containing authentication details
            Example:
            {
                "authentication": {
                    "tenant_id": "xxx",
                    "client_id": "xxx",
                    "client_secret": "xxx"
                },
                "sharepoint": {
                    "site_hostname": "bytfde.sharepoint.com",
                    "site_path": "/sites/clabotconsole",
                    "drive_name": "Documents"
                }
            }
        file_path (str): Relative file path in SharePoint
            Example: "Permanent/8e59c80f-f221-4772-a80d-7aa86e340fe1/samy_20260102_183058_730.pdf"

    Returns:
        Tuple: (status_code, status_description, error_message, base64_string)
    """
    try:
        # -------------------------------
        # 1. Validate Input
        # -------------------------------
        if not credentials or not isinstance(credentials, dict):
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "credentials must be a valid dictionary"
            )

        if not file_path or not isinstance(file_path, str) or not file_path.strip():
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "file_path must be a non-empty string"
            )

        # -------------------------------
        # 2. Extract Credentials
        # -------------------------------
        try:
            auth = credentials["authentication"]
            sp = credentials["sharepoint"]
            tenant_id = auth["tenant_id"]
            client_id = auth["client_id"]
            client_secret = auth["client_secret"]
            site_hostname = sp["site_hostname"]
            site_path = sp["site_path"]
            drive_name = sp["drive_name"]
        except KeyError as e:
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                f"Missing required credential field: {str(e)}"
            )

        # Validate extracted values
        if not all([tenant_id, client_id, client_secret, site_hostname, site_path, drive_name]):
            raise utils.CustomValidationException(
                config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001,
                "One or more credential fields are empty"
            )

        # -------------------------------
        # 3. Authenticate and Get SharePoint IDs
        # -------------------------------
        token = get_access_token(tenant_id, client_id, client_secret)
        site_id = get_site_id(token, site_hostname, site_path)
        drive_id = get_drive_id(token, site_id, drive_name)

        # -------------------------------
        # 4. Download File from SharePoint
        # -------------------------------
        # URL encode the file path to handle special characters
        encoded_path = quote(file_path.strip(), safe='/')

        download_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}:/content"
        headers = {"Authorization": f"Bearer {token}"}

        response = requests.get(download_url, headers=headers)

        # Handle 404 separately for clearer error message
        if response.status_code == 404:
            raise utils.CustomValidationException(
                config.STATUS_NO_DATA_FOUND,
                config.DESC_MSG0003,
                f"File not found in SharePoint: {file_path}"
            )

        # Raise for other HTTP errors
        response.raise_for_status()

        # -------------------------------
        # 5. Convert to Base64
        # -------------------------------
        file_bytes = response.content

        if not file_bytes:
            raise utils.CustomValidationException(
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                "Downloaded file is empty"
            )

        base64_string = base64.b64encode(file_bytes).decode('utf-8')

        return (
            config.STATUS_SUCCESS,
            "Success",
            "",
            base64_string
        )

    except utils.CustomValidationException as e:
        return e.status_code, e.status_description, e.error_message, ""

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == config.STATUS_AUTHENTICATION_FAILED:
            return (
                config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005,
                f"SharePoint authentication failed: {str(e)}",
                ""
            )
        else:
            return (
                config.STATUS_SYSTEM_EXCEPTION,
                config.DESC_MSG0004,
                f"HTTP error downloading file from SharePoint: {str(e)}",
                ""
            )

    except Exception as e:
        return (
            config.STATUS_SYSTEM_EXCEPTION,
            config.DESC_MSG0004,
            f"Failed to download file from SharePoint: {str(e)}",
            ""
        )

