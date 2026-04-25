"""
PetPal - 审计日志服务

提供自动化的审计日志记录：
- 装饰器方式记录敏感操作
- 中间件方式记录请求
- 支持异步记录
"""
from functools import wraps
from datetime import datetime
from typing import Optional, Callable, Any
from fastapi import Request
from sqlalchemy.orm import Session
from loguru import logger


class AuditAction:
    """审计动作常量"""
    # 用户相关
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_REGISTER = "user_register"
    USER_UPDATE_PROFILE = "user_update_profile"
    USER_CHANGE_PASSWORD = "user_change_password"
    USER_STATUS_CHANGE = "user_status_change"
    USER_ROLE_CHANGE = "user_role_change"

    # 内容相关
    POST_CREATE = "post_create"
    POST_UPDATE = "post_update"
    POST_DELETE = "post_delete"
    POST_REVIEW = "post_review"
    COMMENT_DELETE = "comment_delete"

    # 订单相关
    ORDER_CREATE = "order_create"
    ORDER_PAY = "order_pay"
    ORDER_CANCEL = "order_cancel"
    ORDER_REFUND = "order_refund"
    ORDER_SHIP = "order_ship"

    # 管理操作
    ADMIN_BAN_USER = "admin_ban_user"
    ADMIN_UNBAN_USER = "admin_unban_user"
    ADMIN_DELETE_CONTENT = "admin_delete_content"
    ADMIN_UPDATE_CONFIG = "admin_update_config"

    # 敏感数据访问
    ACCESS_USER_DATA = "access_user_data"
    EXPORT_DATA = "export_data"


class AuditLogger:
    """审计日志记录器"""

    @staticmethod
    def log(
        db: Session,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: str = "",
        user_agent: str = "",
        extra_data: Optional[dict] = None
    ):
        """
        记录审计日志

        Args:
            db: 数据库会话
            user_id: 操作用户ID
            action: 操作类型
            resource_type: 资源类型
            resource_id: 资源ID
            old_value: 旧值
            new_value: 新值
            reason: 操作原因
            ip_address: IP地址
            user_agent: 用户代理
            extra_data: 额外数据
        """
        try:
            from app.models.audit_log import AuditLog
            import json

            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent[:500] if user_agent else None,
                extra_data=json.dumps(extra_data) if extra_data else None
            )
            db.add(audit_log)
            db.commit()

            logger.info(
                f"[Audit] user={user_id} action={action} "
                f"resource={resource_type}:{resource_id}"
            )

        except Exception as e:
            logger.error(f"[Audit] 记录审计日志失败: {str(e)}")
            db.rollback()

    @staticmethod
    async def log_async(
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        reason: Optional[str] = None,
        ip_address: str = "",
        user_agent: str = "",
        extra_data: Optional[dict] = None
    ):
        """异步记录审计日志"""
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            AuditLogger.log(
                db=db,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                ip_address=ip_address,
                user_agent=user_agent,
                extra_data=extra_data
            )
        finally:
            db.close()


def audit_log(
    action: str,
    resource_type: str,
    get_resource_id: Optional[Callable] = None,
    get_old_value: Optional[Callable] = None,
    get_new_value: Optional[Callable] = None,
    get_reason: Optional[Callable] = None
):
    """
    审计日志装饰器

    用于自动记录API操作的审计日志

    Example:
        @audit_log(
            action=AuditAction.POST_DELETE,
            resource_type="post",
            get_resource_id=lambda args, kwargs, result: kwargs.get("post_id")
        )
        async def delete_post(post_id: int, ...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 执行原函数
            result = await func(*args, **kwargs)

            # 提取审计信息
            try:
                # 从kwargs中获取request和db
                request = kwargs.get("request")
                db = kwargs.get("db")
                current_user = kwargs.get("current_user")

                if not current_user or not db:
                    return result

                # 获取资源ID
                resource_id = None
                if get_resource_id:
                    resource_id = get_resource_id(args, kwargs, result)

                # 获取旧值
                old_value = None
                if get_old_value:
                    old_value = get_old_value(args, kwargs, result)

                # 获取新值
                new_value = None
                if get_new_value:
                    new_value = get_new_value(args, kwargs, result)

                # 获取原因
                reason = None
                if get_reason:
                    reason = get_reason(args, kwargs, result)

                # 获取IP和UA
                ip_address = ""
                user_agent = ""
                if request:
                    ip_address = request.client.host if request.client else ""
                    user_agent = request.headers.get("user-agent", "")

                # 记录日志
                AuditLogger.log(
                    db=db,
                    user_id=current_user.id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    old_value=old_value,
                    new_value=new_value,
                    reason=reason,
                    ip_address=ip_address,
                    user_agent=user_agent
                )

            except Exception as e:
                logger.error(f"[Audit] 装饰器记录失败: {str(e)}")

            return result
        return wrapper
    return decorator


def get_client_ip(request: Request) -> str:
    """获取客户端真实IP"""
    # 尝试从代理头获取
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    # 直接获取
    if request.client:
        return request.client.host

    return ""


class AuditMiddleware:
    """审计中间件 - 记录敏感操作请求"""

    # 需要记录的敏感路径
    SENSITIVE_PATHS = [
        "/api/v1/admin/",
        "/api/v1/users/",
        "/api/v1/shop/orders/",
    ]

    # 需要记录的HTTP方法
    AUDIT_METHODS = ["POST", "PUT", "DELETE", "PATCH"]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # 检查是否需要审计
        should_audit = (
            request.method in self.AUDIT_METHODS and
            any(request.url.path.startswith(p) for p in self.SENSITIVE_PATHS)
        )

        if should_audit:
            # 记录请求开始
            start_time = datetime.now()
            path = request.url.path

            # 处理请求
            await self.app(scope, receive, send)

            # 记录请求结束（简化记录，详细记录在各API中）
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"[Audit] {request.method} {path} "
                f"ip={get_client_ip(request)} duration={duration:.3f}s"
            )
        else:
            await self.app(scope, receive, send)


# ==================== 便捷函数 ====================

def log_login(db: Session, user_id: int, ip: str, success: bool, reason: str = ""):
    """记录登录日志"""
    from app.models.login_log import LoginLog

    login_log = LoginLog(
        user_id=user_id,
        ip_address=ip,
        status="success" if success else "failed",
        fail_reason=reason if not success else None
    )
    db.add(login_log)
    db.commit()


def log_user_action(
    db: Session,
    user_id: int,
    action: str,
    target_type: str,
    target_id: int = None,
    details: str = "",
    ip: str = ""
):
    """快速记录用户操作"""
    AuditLogger.log(
        db=db,
        user_id=user_id,
        action=action,
        resource_type=target_type,
        resource_id=target_id,
        reason=details,
        ip_address=ip
    )


def log_admin_action(
    db: Session,
    admin_id: int,
    action: str,
    target_type: str,
    target_id: int,
    old_value: str = None,
    new_value: str = None,
    reason: str = "",
    ip: str = ""
):
    """快速记录管理员操作"""
    AuditLogger.log(
        db=db,
        user_id=admin_id,
        action=action,
        resource_type=target_type,
        resource_id=target_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        ip_address=ip,
        extra_data={"admin_action": True}
    )


def log_sensitive_access(
    db: Session,
    user_id: int,
    data_type: str,
    data_id: int,
    access_reason: str = "",
    ip: str = ""
):
    """记录敏感数据访问"""
    AuditLogger.log(
        db=db,
        user_id=user_id,
        action=AuditAction.ACCESS_USER_DATA,
        resource_type=data_type,
        resource_id=data_id,
        reason=access_reason,
        ip_address=ip,
        extra_data={"sensitive_access": True}
    )
