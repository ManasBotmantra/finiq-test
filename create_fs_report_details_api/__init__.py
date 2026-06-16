"""This module provides an Azure Function to insert or upsert Financial Statement (FS) Report Details records."""

import datetime
import json
from zoneinfo import ZoneInfo

import azure.functions as func

from admin_functions import fs_report_details
from common_functions import authorization, config, utils


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """
    Azure Function to create/update Financial Statement Report Details entries.

    Request:
        Headers:
            - request_type: application/json
            - authorize_token: str
        Body (can be a list of records or a dictionary containing records):
            [
                {
                    "tb_id": "uuid-string",
                    "fs_type": "BS",
                    "fs_node_id": "uuid-string", (optional)
                    "fs_node_name": "string",
                    "parent_fs_node_id": "uuid-string", (optional/nullable)
                    "node_seq": 1,
                    "reporting_node_flag": false,
                    "balance": 0.00 (optional/nullable)
                },
                ...
            ]
            OR
            {
                "records": [ ... ]
            }

    Returns:
        JSON response with status_code, status_description, and error_message.
    """

    request_id = context.invocation_id
    api_name = "create_fs_report_details"
    timestamp = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
    input_json = {}

    try:
        # 1. Validate content type
        if req.headers.get('request_type') != 'application/json':
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, "", timestamp,
                {}, config.STATUS_INVALID_INPUT,
                config.DESC_MSG0001, config.ERR_MSG0001
            )
            return func.HttpResponse(
                json.dumps({
                    "status_code": config.STATUS_INVALID_INPUT,
                    "status_description": config.DESC_MSG0001,
                    "error_message": config.ERR_MSG0001
                }),
                mimetype="application/json",
                status_code=402
            )

        # 2. Authenticate using authorize_token
        authorize_token = req.headers.get('authorize_token', '')
        token_status, creator_user_id = authorization.f_validate_authorize_token(authorize_token)
        if token_status == "ERROR":
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, "", timestamp,
                {}, config.STATUS_AUTHENTICATION_FAILED,
                config.DESC_MSG0005, config.ERR_MSG0014
            )
            return func.HttpResponse(
                json.dumps({
                    "status_code": config.STATUS_AUTHENTICATION_FAILED,
                    "status_description": config.DESC_MSG0005,
                    "error_message": config.ERR_MSG0014
                }),
                mimetype="application/json",
                status_code=401
            )

        # 3. Parse request body
        body_bytes = req.get_body()
        if not body_bytes or body_bytes.strip() == b'':
            # Fallback to reading from local file
            import os
            app_root = os.path.dirname(context.function_directory)
            fallback_file = os.path.join(app_root, "fs_report_details.json")
            try:
                with open(fallback_file, "r", encoding="utf-8") as f:
                    req_body = json.load(f)
            except Exception as e:
                utils.f_log_audit_trail(
                    "ERROR", request_id, api_name, creator_user_id, timestamp,
                    {}, config.STATUS_SYSTEM_EXCEPTION,
                    config.DESC_MSG0004, f"Failed to load fallback file: {str(e)}"
                )
                return func.HttpResponse(
                    json.dumps({
                        "status_code": config.STATUS_SYSTEM_EXCEPTION,
                        "status_description": config.DESC_MSG0004,
                        "error_message": "Failed to load fallback file"
                    }),
                    mimetype="application/json",
                    status_code=500
                )
        else:
            try:
                req_body = req.get_json()
            except ValueError:
                utils.f_log_audit_trail(
                    "ERROR", request_id, api_name, creator_user_id, timestamp,
                    {}, config.STATUS_INVALID_INPUT,
                    config.DESC_MSG0001, "Invalid JSON in request body"
                )
                return func.HttpResponse(
                    json.dumps({
                        "status_code": config.STATUS_INVALID_INPUT,
                        "status_description": config.DESC_MSG0001,
                        "error_message": "Invalid JSON in request body"
                    }),
                    mimetype="application/json",
                    status_code=402
                )

        input_json = json.dumps(req_body)

        # Handle body formats: list or dict
        if isinstance(req_body, list):
            records = req_body
        elif isinstance(req_body, dict):
            records = req_body.get('records') or req_body.get('fs_report_details') or req_body.get('fs_details')
            if records is None:
                # If neither key is found, check if it's a single record dictionary and wrap it in a list
                if all(k in req_body for k in ["tb_id", "fs_type", "fs_node_name"]):
                    records = [req_body]
                else:
                    raise ValueError("Could not find records list in request payload")
        else:
            raise ValueError("Payload must be a list or dictionary")

        # 4. Call business logic
        status_code, status_description, error_message, response_body = fs_report_details.f_insert_fs_report_details(
            records=records,
            connection=None
        )

        # 5. Handle error response
        if status_code != config.STATUS_SUCCESS:
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, creator_user_id or "", timestamp,
                input_json, status_code, status_description, error_message
            )
            return func.HttpResponse(
                json.dumps({
                    "status_code": status_code,
                    "status_description": status_description,
                    "error_message": error_message if status_code != config.STATUS_SYSTEM_EXCEPTION else "SOMETHING WENT WRONG"
                }),
                mimetype="application/json",
                status_code=status_code
            )

        # 6. Success response
        final_response = utils.f_generate_response(
            status_code, status_description, error_message, response_body
        )

        utils.f_log_audit_trail(
            "INFO",
            request_id,
            api_name,
            creator_user_id or "",
            timestamp,
            input_json,
            status_code,
            status_description,
            error_message
        )

        return func.HttpResponse(
            json.dumps(final_response),
            mimetype="application/json",
            status_code=status_code
        )

    except Exception as e:
        utils.f_log_audit_trail(
            "ERROR", request_id, api_name, "", timestamp,
            input_json, config.STATUS_SYSTEM_EXCEPTION,
            config.DESC_MSG0004, str(e)
        )
        return func.HttpResponse(
            json.dumps({
                "status_code": config.STATUS_SYSTEM_EXCEPTION,
                "status_description": config.DESC_MSG0004,
                "error_message": "SOMETHING WENT WRONG"
            }),
            mimetype="application/json",
            status_code=400
        )
