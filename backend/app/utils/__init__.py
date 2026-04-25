"""
PetPal - 工具模块初始化
"""
from app.utils.security import verify_password, hash_password, create_access_token, verify_token
from app.utils.deps import get_current_user, get_current_user_optional, require_role
from app.utils.response import success, error, page_response
from app.utils.data_masking import (
    mask_phone, mask_email, mask_id_card, mask_bank_card,
    mask_name, mask_address, mask_ip, DataMasker
)
from app.utils.ip_resolver import (
    resolve_ip, get_location_string, check_location_change,
    is_private_ip, ip_resolver
)
from app.utils.ua_parser import (
    parse_user_agent, get_device_info_string, is_mobile_device,
    is_known_bot, ua_parser
)
from app.utils.xss_filter import (
    clean_html, strip_tags, escape_html, sanitize_text,
    sanitize_url, sanitize_filename, check_content_safety,
    ContentSanitizer
)
from app.utils.file_validator import (
    validate_file, validate_upload_file, process_upload_file,
    detect_mime_type, sanitize_filename as safe_filename,
    generate_safe_filename, generate_file_path,
    calculate_file_hash, scan_for_malware,
    FileValidator, MalwareScanResult,
    ALLOWED_FILE_TYPES, DANGEROUS_EXTENSIONS
)
from app.utils.sql_guard import (
    is_safe_string, detect_sql_injection, escape_sql_string,
    sanitize_search_query, sanitize_identifier,
    SafeOrderBy, SafePagination, SafeQueryBuilder,
    validate_sql_params, safe_like_pattern,
    validate_table_name, validate_column_names,
    SQLGuard, sql_guard
)

__all__ = [
    # Security
    "verify_password", "hash_password", "create_access_token", "verify_token",
    # Dependencies
    "get_current_user", "get_current_user_optional", "require_role",
    # Response
    "success", "error", "page_response",
    # Data Masking
    "mask_phone", "mask_email", "mask_id_card", "mask_bank_card",
    "mask_name", "mask_address", "mask_ip", "DataMasker",
    # IP Resolution
    "resolve_ip", "get_location_string", "check_location_change",
    "is_private_ip", "ip_resolver",
    # User-Agent Parsing
    "parse_user_agent", "get_device_info_string", "is_mobile_device",
    "is_known_bot", "ua_parser",
    # XSS Filter
    "clean_html", "strip_tags", "escape_html", "sanitize_text",
    "sanitize_url", "sanitize_filename", "check_content_safety",
    "ContentSanitizer",
    # File Validator
    "validate_file", "validate_upload_file", "process_upload_file",
    "detect_mime_type", "safe_filename", "generate_safe_filename",
    "generate_file_path", "calculate_file_hash", "scan_for_malware",
    "FileValidator", "MalwareScanResult",
    "ALLOWED_FILE_TYPES", "DANGEROUS_EXTENSIONS",
    # SQL Guard
    "is_safe_string", "detect_sql_injection", "escape_sql_string",
    "sanitize_search_query", "sanitize_identifier",
    "SafeOrderBy", "SafePagination", "SafeQueryBuilder",
    "validate_sql_params", "safe_like_pattern",
    "validate_table_name", "validate_column_names",
    "SQLGuard", "sql_guard",
]
