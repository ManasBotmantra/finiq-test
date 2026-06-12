"""This module provides an Azure Function to create a COA node in the coa_master table."""

import datetime
import json

import azure.functions as func

from admin_functions import coa
from common_functions import config, utils

# UTC+05:30 (Asia/Kolkata) without requiring tzdata
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    """
    Creates a Chart of Accounts (COA) node entry based on the input.

    Request:
        Headers:
            - request_type = application/json

        Body:
        {
            "company_id": "uuid-string",
            "coa_node_code": "string",          (optional)
            "coa_node_name": "string",          (optional)
            "parent_coa_node_id": "uuid-string", (optional)
            "posting_ledger_flag": true/false
        }

    Returns:
        JSON response with status_code, status_description, error_message,
        and coa_node_id on success.
    """
    request_id = context.invocation_id
    api_name = "create_coa_node"
    timestamp = datetime.datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
    input_json = {}
    user_id = None

    try:
        # =================================================================
        # 1. Validate request type
        # =================================================================
        if req.headers.get('request_type') != 'application/json':
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, user_id, timestamp, {},
                config.STATUS_INVALID_INPUT, config.DESC_MSG0001, config.ERR_MSG0001
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

        # =================================================================
        # 2. Parse request body
        # =================================================================
        try:
            req_body = req.get_json()
        except ValueError:
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, user_id, timestamp, {},
                config.STATUS_INVALID_INPUT, config.DESC_MSG0006, config.ERR_MSG0013
            )
            return func.HttpResponse(
                json.dumps({
                    "status_code": config.STATUS_INVALID_INPUT,
                    "status_description": config.DESC_MSG0006,
                    "error_message": config.ERR_MSG0013
                }),
                mimetype="application/json",
                status_code=402
            )

        input_json = json.dumps(req_body)

        # =================================================================
        # 3. Extract and validate required fields
        # =================================================================
        company_id = req_body.get('company_id', '')
        coa_node_code = req_body.get('coa_node_code', '')
        coa_node_name = req_body.get('coa_node_name', '')
        parent_coa_node_id = req_body.get('parent_coa_node_id', '')
        posting_ledger_flag = req_body.get('posting_ledger_flag')

        # company_id is required
        if not company_id:
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, user_id, timestamp, input_json,
                config.STATUS_INVALID_INPUT, config.DESC_MSG0006, config.ERR_MSG0005
            )
            return func.HttpResponse(
                json.dumps({
                    "status_code": config.STATUS_INVALID_INPUT,
                    "status_description": config.DESC_MSG0006,
                    "error_message": config.ERR_MSG0005
                }),
                mimetype="application/json",
                status_code=402
            )

        # posting_ledger_flag is required
        if posting_ledger_flag is None:
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, user_id, timestamp, input_json,
                config.STATUS_INVALID_INPUT, config.DESC_MSG0006, config.ERR_MSG0006
            )
            return func.HttpResponse(
                json.dumps({
                    "status_code": config.STATUS_INVALID_INPUT,
                    "status_description": config.DESC_MSG0006,
                    "error_message": config.ERR_MSG0006
                }),
                mimetype="application/json",
                status_code=402
            )

        # posting_ledger_flag must be boolean
        if not isinstance(posting_ledger_flag, bool):
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, user_id, timestamp, input_json,
                config.STATUS_INVALID_INPUT, config.DESC_MSG0006, config.ERR_MSG0011
            )
            return func.HttpResponse(
                json.dumps({
                    "status_code": config.STATUS_INVALID_INPUT,
                    "status_description": config.DESC_MSG0006,
                    "error_message": config.ERR_MSG0011
                }),
                mimetype="application/json",
                status_code=402
            )

        # =================================================================
        # 4. Call business logic
        # =================================================================
        status_code, status_description, error_message, coa_node_id = coa.f_create_coa_node(
            company_id, coa_node_code, coa_node_name,
            parent_coa_node_id, posting_ledger_flag
        )

        if status_code != config.STATUS_SUCCESS:
            utils.f_log_audit_trail(
                "ERROR", request_id, api_name, user_id, timestamp, input_json,
                status_code, status_description, error_message
            )
            response_json = utils.f_generate_response(
                status_code, status_description,
                error_message if status_code != config.STATUS_SYSTEM_EXCEPTION else "SOMETHING WENT WRONG"
            )
            return func.HttpResponse(
                json.dumps(response_json),
                mimetype="application/json",
                status_code=status_code
            )

        # =================================================================
        # 5. Success — build response with generated coa_node_id
        # =================================================================
        response_json = utils.f_generate_response(
            status_code, status_description, error_message,
            coa_node_id=coa_node_id
        )

        utils.f_log_audit_trail(
            "INFO", request_id, api_name, user_id, timestamp, input_json,
            status_code, status_description, error_message
        )

        return func.HttpResponse(
            json.dumps(response_json),
            mimetype="application/json",
            status_code=status_code
        )

    except Exception as e:
        utils.f_log_audit_trail(
            "ERROR", request_id, api_name, "", timestamp,
            input_json, config.STATUS_SYSTEM_EXCEPTION, config.DESC_MSG0004, str(e)
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
