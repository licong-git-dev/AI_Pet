"""
PetPal - 服务模块初始化
"""
from app.services.ai_health import (
    analyze_pet_health,
    generate_consultation_response,
    generate_consultation_summary
)
from app.services.sms_service import (
    send_sms_code,
    verify_sms_code,
    generate_code,
    get_code_ttl,
    get_rate_limit_ttl
)
from app.services.login_log_service import (
    record_login,
    check_login_risk,
    check_abnormal_login,
    get_user_login_history,
    get_recent_login_locations,
    count_recent_failures,
    cleanup_old_logs
)
from app.services.audit_log_service import (
    create_audit_log,
    log_user_action,
    get_audit_logs,
    get_resource_history,
    get_user_activity,
    get_audit_statistics,
    cleanup_old_audit_logs,
    audit_log,
    AuditLogger
)

__all__ = [
    # AI健康服务
    "analyze_pet_health",
    "generate_consultation_response",
    "generate_consultation_summary",
    # 短信服务
    "send_sms_code",
    "verify_sms_code",
    "generate_code",
    "get_code_ttl",
    "get_rate_limit_ttl",
    # 登录日志服务
    "record_login",
    "check_login_risk",
    "check_abnormal_login",
    "get_user_login_history",
    "get_recent_login_locations",
    "count_recent_failures",
    "cleanup_old_logs",
    # 审计日志服务
    "create_audit_log",
    "log_user_action",
    "get_audit_logs",
    "get_resource_history",
    "get_user_activity",
    "get_audit_statistics",
    "cleanup_old_audit_logs",
    "audit_log",
    "AuditLogger",
]
