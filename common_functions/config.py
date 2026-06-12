"""This module provides configuration settings for the application, including schema names, file sizes, Azure Blob Storage configurations, logging settings, authentication parameters, status codes, and error messages."""


import os

from dotenv import load_dotenv

load_dotenv()
SCHEMANAME = os.getenv("SCHEMANAME", "public")

#FILE SIZE
MAX_FILE_SIZE_MB = os.getenv("MAX_FILE_SIZE_MB", "10")

# Azure Blob Storage Configuration
CONTAINER_URL = os.getenv("CONTAINER_URL", "")
CONTAINER_SAS_TOKEN = os.getenv("CONTAINER_SAS_TOKEN", "")

# JSON File Paths
INPUT_TEMP_FILE_PATH = os.getenv(
    "INPUT_TEMP_FILE_PATH", "TEMP")
EMBEDDING_FOLDER_PATH = os.getenv("EMBEDDINGS_FOLDER_PATH")


# Logging Configuration
LOG_INFO = os.getenv("LOG_INFO", "TRUE").upper() == "TRUE"
LOG_WARNING = os.getenv("LOG_WARNING", "TRUE").upper() == "TRUE"
LOG_ERROR = os.getenv("LOG_ERROR", "TRUE").upper() == "TRUE"

# AUTHENTICATION Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "")
TOKEN_EXPIRY_LIMIT = int(os.getenv("TOKEN_EXPIRY_LIMIT", "3600"))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM","HS256")

# EMAIL Configuration
EMAIL_TOKEN_EXPIRY_LIMIT = int(
    os.getenv("EMAIL_TOKEN_EXPIRY_LIMIT", "1800"))
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
FRONTEND_RESET_URL = os.getenv("FRONTEND_RESET_URL", "")

USER_ID_FOR_BOT = "SYSTEM"
MAX_DASHBOARD_LIMIT=1000
DASHBOARD_STATEMENT_TIMEOUT_MS = 60000  # 60 seconds
MAX_CONCURRENT_CALLS = 5

# Status Codes
STATUS_SUCCESS = 200
STATUS_SYSTEM_EXCEPTION = 400
STATUS_AUTHENTICATION_FAILED = 401
STATUS_INVALID_INPUT = 402
STATUS_NO_DATA_FOUND = 403
STATUS_DUPLICATE_DATA = 404


# status description MSG
DESC_MSG0001 = "INVALID INPUT"
DESC_MSG0002 = "DATA ERROR"
DESC_MSG0003 = "NO DATA FOUND"
DESC_MSG0004 = "SYSTEM EXCEPTION"
DESC_MSG0005 = "AUTHORIZATION FAILED"
DESC_MSG0006 = "DUPLICATE DATA"
DESC_MSG0007 = "SUCCESS"
DESC_MSG0008 = "ACCESS DENIED"
DESC_MSG0009 = "FAIL"
DESC_MSG0010 = "INSUFFICIENT_BALANCE"

# Error Messages
ERR_MSG0001 = "Request type must be application/json"
ERR_MSG0002 = "User ID and password are required"
ERR_MSG0003 = "Invalid credentials or user is not active"
ERR_MSG0004 = "Error generating authorize token"
ERR_MSG0005 = "Missing required key"
ERR_MSG0006 = "key, api name and authorize token field not be empty"
ERR_MSG0007 = "Token decryption failed."
ERR_MSG0008 = "Key or key with api name is not available in key master and key api master"
ERR_MSG0009 = "{org_name} org is not active in org_master"
ERR_MSG0010 = "Database connection failed"
ERR_MSG0011 = "Token is outside allowed window"
ERR_MSG0012 = "user with org not found in user_org_master"
ERR_MSG0013 = "key and authorize token field not be empty"
ERR_MSG0014 = "Invalid authorize token"
ERR_MSG0015 = "Key does not have balance"
ERR_MSG0016 = "key not found in key_master or org_name is not matched with user_org_master"
ERR_MSG0017 = "Missing required field(s): 'api_name' or 'api_config'"
ERR_MSG0018 = "Invalid input"
ERR_MSG0019 = "API '{str_api_name}' not found in api master table"
ERR_MSG0020 = "Invalid default JSON format"
ERR_MSG0021 = "Invalid type for json_api_config"
ERR_MSG0022 = "user_id, password, name, and role are required fields."
ERR_MSG0023 = "user_id, password, name, and role must be strings."
ERR_MSG0024 = "Invalid user_id format. Must be a valid email address."
ERR_MSG0025 = "allowed roles are: {allowed_roles}"
ERR_MSG0026 = "org_name must be a list of strings."
ERR_MSG0027 = "User with user_id '{user_id}' already exists"
ERR_MSG0028 = "No user found with the provided criteria. Please check the user_id or org_name."
ERR_MSG0029 = "search_fields cannot be empty or contain empty values"
ERR_MSG0030 = "No user found with the provided user_id '{user_id}'"
ERR_MSG0031 = "user_status must be either 'Active' or 'Inactive"
ERR_MSG0032 = "User with ID '{user_id}' not found."
ERR_MSG0033 = "Invalid created_on_operator"
ERR_MSG0034 = "Invalid modified_on_operator"
ERR_MSG0035 = "No data found for the given filters in key api config."
ERR_MSG0036 = "No completion_config records found for the given filters."
ERR_MSG0037 = "All required fields must be provided."
ERR_MSG0038 = "input_token_ratio' must be less than or equal to 1."
ERR_MSG0039 = "'input_token_ratio' must be a number and  must be less than or equal to 1."
ERR_MSG0040 = "Duplicate key and completion_model found."
ERR_MSG0041 = "Input must be a dictionary."
ERR_MSG0042 = "Both 'key' and 'completion_model' in search_fields are required."
ERR_MSG0043 = "'completion_config_status' must be either 'Active' or 'Inactive'."
ERR_MSG0044 = "At least one update field must be provided."
ERR_MSG0045 = "No matching record found to update."
ERR_MSG0046 = "No prompt_config records found for the given filters."
ERR_MSG0047 = "Duplicate key, completion_model, and template found."
ERR_MSG0048 = "All search fields and 'modified_by' must be provided."
ERR_MSG0049 = "No records found matching the criteria"
ERR_MSG0050 = "Missing or empty required field: {field}"
ERR_MSG0051 = "Duplicate credential record exists"
ERR_MSG0052 = "Missing or empty required search field: {key}"
ERR_MSG0053 = "Missing or empty required field: modified_by"
ERR_MSG0054 = "Missing or empty required update field: {update_fields}"
ERR_MSG0055 = "No data found to update with the given criteria"
ERR_MSG0056 = "No embedding configuration found matching given filters"
ERR_MSG0057 = "Invalid or inactive key"
ERR_MSG0058 = "Invalid vector search algorithm"
ERR_MSG0059 = "Invalid or inactive embed LLM type or not found"
ERR_MSG0060 = "Duplicate record"
ERR_MSG0061 = "key (primary key) cannot be empty"
ERR_MSG0062 = "key_name cannot be empty"
ERR_MSG0063 = "org_name cannot be empty"
ERR_MSG0064 = "Invalid key_status: '{key_status}'. Allowed statuses: {allowed_status}"
ERR_MSG0065 = "Key '{key}' already exists"
ERR_MSG0066 = "search_fields.key cannot be empty"
ERR_MSG0067 = "update_fields cannot be empty"
ERR_MSG0068 = "No valid fields to update provided"
ERR_MSG0069 = "Missing required fields 'key' or 'api_name'."
ERR_MSG0070 = "total_key_balance must be a numeric value"
ERR_MSG0071 = "available_key_balance must be a numeric value."
ERR_MSG0072 = "total_key_balance must be greater than or equal to available_key_balance."
ERR_MSG0073 = "Duplicate key-api combination exists."
ERR_MSG0074 = "Search fields must be provided and non-empty."
ERR_MSG0075 = "user_id is needed"
ERR_MSG0076 = "No active keys with active orgs found"
ERR_MSG0077 = "No active orgs found for user"
ERR_MSG0078 = "No records found"
ERR_MSG0079 = "lov_type is required and must be a list of strings."
ERR_MSG0080 = "No LOVs found for the specified type."
ERR_MSG0081 = "No active APIs found."
ERR_MSG0082 = "Invalid input types for org_name or status"
ERR_MSG0083 = "Organization name cannot be empty or non-string"
ERR_MSG0084 = "org_name already exists {org_name}"
ERR_MSG0085 = "Search and update fields cannot be empty."
ERR_MSG0086 = "Invalid value for search field: {key}"
ERR_MSG0087 = "Field '{key}' cannot be empty or None"
ERR_MSG0088 = "Invalid status value. Allowed values are: {allowed}"
ERR_MSG0089 = "No records found for the given filters"
ERR_MSG0090 = "Required fields 'key', 'raw_data_model', and 'request_mode' are missing"
ERR_MSG0091 = "Invalid request_mode: {str_request_mode}"
ERR_MSG0092 = "Search fields 'key' and 'raw_data_model' are required"
ERR_MSG0093 = "default_flag must be 'true' or 'false'"
ERR_MSG0094 = "key, regex_model, regex_continue_flag, and regex_summary are required fields"
ERR_MSG0095 = "regex_config_status must be 'Active' or 'Inactive'"
ERR_MSG0096 = "Duplicate data found for key and regex_model"
ERR_MSG0097 = "regex_summary items must have non-empty field and regex"
ERR_MSG0098 = "Missing key or regex_model in search_fields"
ERR_MSG0099 = "regex_config_status must be 'Active' or 'Inactive'"
ERR_MSG0100 = "default_flag must be 'true' or 'false'"
ERR_MSG0101 = "No matching regex classify config records found."
ERR_MSG0102 = "Invalid input: key, regex_model, and regex_classify are required."
ERR_MSG0103 = "Duplicate regex classify config entry found for key: {str_key} and model: {str_regex_model}"
ERR_MSG0104 = "Key and regex_model are required for search."
ERR_MSG0105 = "Invalid JSON format for regex_classify"
ERR_MSG0106 = "regex_classify must be a list"
ERR_MSG0107 = "Missing classifier or regex"
ERR_MSG0108 = "{str_cred_type} not found in cred_type_master"
ERR_MSG0109 = "Authorization token is required"
ERR_MSG0110 = "Token timestamp missing."
ERR_MSG0111 = "User is not active or does not exist."
ERR_MSG0112 = "Error generating renew authorize token"
ERR_MSG0113 = "Invalid input: key and completion model are required."
ERR_MSG0114 = "No completion config found"
ERR_MSG0115 = "User prompt is required"
ERR_MSG0116 = "No prompt config found"
ERR_MSG0117 = "LLM type not found for key and model"
ERR_MSG0118 = "No prompt found for the given key and completion model"
ERR_MSG0119 = "Org not found for key"
ERR_MSG0120 = "Credential not found for LLM type"
ERR_MSG0121 = "Key and completion model are required."
ERR_MSG0122 = "No active credentials found for the provided key and credential subtype."
ERR_MSG0123 = "Invalid input: key, text, and regex model are required."
ERR_MSG0124 = "No regex_config found for the given filters."
ERR_MSG0125 = "Invalid input: key, text, and regex model are required."
ERR_MSG0126 = "No regex_config found for the given key and model."
ERR_MSG0127 = "regex_summary must be a list"
ERR_MSG0128 = "regex must be a list of list of strings"
ERR_MSG0129 = "'input_token_ratio' is required and cannot be empty and must be greater than 0.0"
ERR_MSG0130 = "duplicate data found for key and regex_model"
ERR_MSG0131 = "regex must be a list of list of Regex/strings"
ERR_MSG0132 = "Invalid regex pattern: {regex_error}"
ERR_MSG0133 = "Digital extraction failed - {stre}"
ERR_MSG0134 = "Blob file path is missing"
ERR_MSG0135 = "Required parameter is missing or empty {str_key, str_blobfile_path, str_request_model, str_api_name}"
ERR_MSG0136 = "No matching data found in key api config table"
ERR_MSG0137 = "Invalid config JSON: {e}"
ERR_MSG0138 = "Required parameter is missing in extract raw data"
ERR_MSG0139 = "No data found in raw_data_config"
ERR_MSG0140 = "failed in identify_pdf_type"
ERR_MSG0141 = "Credential not found for key {str_key} and type {credential_type}"
ERR_MSG0142 = "Failed to extract FR raw text"
ERR_MSG0143 = "Invalid file type detected: {file_type}"
ERR_MSG0144 = "Required parameter is missing in f_extract_document_data"
ERR_MSG0145 = "No matching data found in key api config table"
ERR_MSG0146 = "Unsupported request_mode: {request_mode}"
ERR_MSG0147 = "Missing or empty field: {field_name}"
ERR_MSG0148 = "Key or Api name is not found in key api master table"
ERR_MSG0149 = "Duplicate API config record exists"
ERR_MSG0150 = "Missing or empty required search field"
ERR_MSG0151 = "Missing or empty field: modified_by"
ERR_MSG0152 = "Please provide at least one field to update"
ERR_MSG0153 = "No data found to update"
ERR_MSG0154 = "Failed to extract raw text from XLSX"
ERR_MSG0155 = "Failed to extract raw text from XLS"
ERR_MSG0156 = "Failed to extract raw text from PPTX"
ERR_MSG0157 = "Failed to extract raw text from PPT"
ERR_MSG0158 = "Failed to extract raw text from TXT"
ERR_MSG0159 = "Failed to extract raw text from PDF"
ERR_MSG0160 = "Failed to extract raw text from DOCX"
ERR_MSG0161 = "Failed to extract raw text from DOC"
ERR_MSG0162 = "Failed to extract raw text from XLSX"
ERR_MSG0163 = "Failed to extract raw text from XLS"
ERR_MSG0164 = "Failed to extract raw text from PPTX"
ERR_MSG0165 = "Failed to extract raw text from PPT"
ERR_MSG0166 = "Failed to extract raw text from TXT"
ERR_MSG0167 = "Failed to extract raw text from PDF"

# Company Master Error Messages
ERR_MSG0168 = "Invalid input types for company_name, org_name, or status"
ERR_MSG0169 = "Company name cannot be empty or non-string"
ERR_MSG0170 = "Organization name cannot be empty or non-string"
ERR_MSG0171 = "company_config is required and must be a valid JSON object"
ERR_MSG0172 = "company_cred must be a valid JSON object"
ERR_MSG0173 = "Invalid status value. Allowed values are: {allowed}"
ERR_MSG0174 = "Organization '{org_name}' not found in org_master"
ERR_MSG0175 = "Company '{company_name}' already exists for organization '{org_name}'"
ERR_MSG0176 = "Field '{field}' must be a valid JSON object"

# Company Module Master Error Messages
ERR_MSG0177 = "company_id cannot be empty or non-string"
ERR_MSG0178 = "module_code cannot be empty or non-string"
ERR_MSG0179 = "config_type cannot be empty or non-string"
ERR_MSG0180 = "module_config_json is required and must be a valid JSON object"
ERR_MSG0181 = "Company with company_id '{company_id}' not found in company_master"
ERR_MSG0182 = "Company module already exists for company_id '{company_id}', module_code '{module_code}'"

# Org Module Master Error Messages
ERR_MSG0183 = "Org module mapping already exists for org_name '{org_name}' and module_code '{module_code}'"
ERR_MSG0184 = "Org module mapping with org_name '{org_name}' and module_code '{module_code}' not found"

# Tally Purchase LOV Error Messages
ERR_MSG0185 = "Company with company_id '{company_id}' and org_name '{org_name}' not found or not active in company_master"


ACTIVE_STATUS = "ACTIVE"
LLMs_WITH_NO_TEMERATURE = ["o4-mini-2"]
