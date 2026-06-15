"""This module provides an Azure Function to create a Trial Balance with details."""

import datetime
import json
from zoneinfo import ZoneInfo

import azure.functions as func

from admin_functions import trial_balance
from common_functions import authorization, config, utils


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """
    Azure Function to create a Trial Balance and insert its details.

    Request:
        Headers:
            - request_type: application/json
            - authorize_token: str
        Body:
            {
                "company_id": "uuid-string",
                "tb_name": "string",
                "from_date": "YYYY-MM-DD",
                "to_date": "YYYY-MM-DD",
                "trial_balance_details": [
                    {
                        "account_name": "string",
                        "account_code": "string", (optional)
                        "opening_balance": float, (optional)
                        "debit": float, (optional)
                        "credit": float, (optional)
                        "closing_balance": float
                    },
                    ...
                ]
            }

    Returns:
        JSON response with status_code, status_description, and error_message.
    """

    request_id = context.invocation_id
    api_name = "create_trial_balance"
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
            fallback_file = os.path.join(app_root, "trial_balance.json")
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

        company_id = req_body.get('company_id', '').strip()
        tb_name = req_body.get('tb_name', '').strip()
        from_date = req_body.get('from_date', '').strip()
        to_date = req_body.get('to_date', '').strip()

        # Extract details (support both direct list or standard JSON formats)
        details = req_body.get('trial_balance_details')
        if not details:
            # Fallback check for "response_body.trial_balance" structure
            details = req_body.get('response_body', {}).get('trial_balance')

        # 4. Call business logic
        status_code, status_description, error_message, response_body = trial_balance.f_insert_trial_balance_with_details(
            company_id=company_id,
            tb_name=tb_name,
            from_date=from_date,
            to_date=to_date,
            details=details,
            creator_user_id=creator_user_id
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
