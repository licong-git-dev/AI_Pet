"""
PetPal - 审计日志服务

提供敏感操作的审计日志记录功能，用于：
- 安全合规审计
- 操作追踪和问题排查
- 用户行为分析
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from functools import wraps

from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from fastapi import Request
from loguru import logger

from app.models.audit_log import AuditLog, AuditAction, AuditResource
from app.database import get_db


def create_audit_log(
    db: Session,
    action: str,
    resource_type: str,
    user_id: Optional[int] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    action_desc: Optional[str] = None,
    old_value: Optional[Dict] = None,
    new_value: Optional[Dict] = None,
    changes: Optional[Dict] = None,
    request_ip: Optional[str] = None,
    request_location: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> AuditLog:
    """创建审计日志

    Args:
        db: 数据库会话
        action: 操作类型 (create/update/delete/login等)
        resource_type: 资源类型 (user/pet/post等)
        user_id: 操作用户ID
        resource_id: 资源ID
        resource_name: 资源名称
        action_desc: 操作描述
        old_value: 变更前的值
        new_value: 变更后的值
        changes: 具体变更字段
        request_ip: 请求IP
        request_location: 请求地点
        user_agent: User-Agent
        request_id: 请求ID
        status: 操作状态 (success/failure)
        error_message: 错误信息

    Returns:
        创建的审计日志记录
    """
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        action_desc=action_desc,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        resource_name=resource_name,
        old_value=old_value,
        new_value=new_value,
        changes=changes,
        request_ip=request_ip,
        request_location=request_location,
        user_agent=user_agent,
        request_id=request_id,
        status=status,
        error_message=error_message,
        created_at=datetime.now(),
    )

    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    # 记录到系统日志
    log_msg = (
        f"Audit | action={action} | resource={resource_type}:{resource_id} | "
        f"user_id={user_id} | status={status}"
    )
    if status == "success":
        logger.info(log_msg)
    else:
        logger.warning(f"{log_msg} | error={error_message}")

    return audit_log


async def log_user_action(
    db: Session,
    request: Request,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    action_desc: Optional[str] = None,
    old_value: Optional[Dict] = None,
    new_value: Optional[Dict] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> AuditLog:
    """记录用户操作（从Request中提取信息）

    Args:
        db: 数据库会话
        request: FastAPI Request对象
        action: 操作类型
        resource_type: 资源类型
        其他参数同 create_audit_log

    Returns:
        创建的审计日志记录
    """
    # 从request中提取用户ID
    user_id = None
    if hasattr(request.state, "user"):
        user_id = request.state.user.id if request.state.user else None

    # 提取请求信息
    request_id = getattr(request.state, "request_id", None)
    request_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    # 计算变更字段
    changes = None
    if old_value and new_value:
        changes = _calculate_changes(old_value, new_value)

    # 解析IP位置
    request_location = None
    if request_ip:
        try:
            from app.utils.ip_resolver import get_location_string
            request_location = get_location_string(request_ip)
        except Exception:
            pass

    return create_audit_log(
        db=db,
        action=action,
        resource_type=resource_type,
        user_id=user_id,
        resource_id=resource_id,
        resource_name=resource_name,
        action_desc=action_desc,
        old_value=old_value,
        new_value=new_value,
        changes=changes,
        request_ip=request_ip,
        request_location=request_location,
        user_agent=user_agent,
        request_id=request_id,
        status=status,
        error_message=error_message,
    )


def _get_client_ip(request: Request) -> str:
    """获取客户端IP"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "127.0.0.1"


def _calculate_changes(old_value: Dict, new_value: Dict) -> Dict:
    """计算两个字典之间的变更"""
    changes = {}
    all_keys = set(old_value.keys()) | set(new_value.keys())

    for key in all_keys:
        old_val = old_value.get(key)
        new_val = new_value.get(key)

        if old_val != new_val:
            changes[key] = {
                "old": old_val,
                "new": new_val
            }

    return changes


async def get_audit_logs(
    db: Session,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    status: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[AuditLog], int]:
    """查询审计日志

    Args:
        db: 数据库会话
        user_id: 用户ID过滤
        action: 操作类型过滤
        resource_type: 资源类型过滤
        resource_id: 资源ID过滤
        status: 状态过滤
        start_time: 开始时间
        end_time: 结束时间
        page: 页码
        page_size: 每页数量

    Returns:
        (审计日志列表, 总数)
    """
    query = db.query(AuditLog)

    # 应用过滤条件
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.filter(AuditLog.resource_id == resource_id)
    if status:
        query = query.filter(AuditLog.status == status)
    if start_time:
        query = query.filter(AuditLog.created_at >= start_time)
    if end_time:
        query = query.filter(AuditLog.created_at <= end_time)

    # 计算总数
    total = query.count()

    # 分页查询
    logs = query.order_by(desc(AuditLog.created_at)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return logs, total


async def get_resource_history(
    db: Session,
    resource_type: str,
    resource_id: str,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[AuditLog], int]:
    """获取资源的操作历史

    Args:
        db: 数据库会话
        resource_type: 资源类型
        resource_id: 资源ID
        page: 页码
        page_size: 每页数量

    Returns:
        (审计日志列表, 总数)
    """
    return await get_audit_logs(
        db=db,
        resource_type=resource_type,
        resource_id=resource_id,
        page=page,
        page_size=page_size,
    )


async def get_user_activity(
    db: Session,
    user_id: int,
    days: int = 30,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[AuditLog], int]:
    """获取用户的操作活动

    Args:
        db: 数据库会话
        user_id: 用户ID
        days: 查询天数
        page: 页码
        page_size: 每页数量

    Returns:
        (审计日志列表, 总数)
    """
    start_time = datetime.now() - timedelta(days=days)
    return await get_audit_logs(
        db=db,
        user_id=user_id,
        start_time=start_time,
        page=page,
        page_size=page_size,
    )


async def get_audit_statistics(
    db: Session,
    days: int = 7,
) -> Dict[str, Any]:
    """获取审计统计信息

    Args:
        db: 数据库会话
        days: 统计天数

    Returns:
        统计数据
    """
    start_time = datetime.now() - timedelta(days=days)

    # 总操作数
    total_count = db.query(AuditLog).filter(
        AuditLog.created_at >= start_time
    ).count()

    # 成功/失败统计
    success_count = db.query(AuditLog).filter(
        and_(
            AuditLog.created_at >= start_time,
            AuditLog.status == "success"
        )
    ).count()

    failure_count = db.query(AuditLog).filter(
        and_(
            AuditLog.created_at >= start_time,
            AuditLog.status == "failure"
        )
    ).count()

    # 按操作类型统计
    from sqlalchemy import func
    action_stats = db.query(
        AuditLog.action,
        func.count(AuditLog.id).label("count")
    ).filter(
        AuditLog.created_at >= start_time
    ).group_by(AuditLog.action).all()

    # 按资源类型统计
    resource_stats = db.query(
        AuditLog.resource_type,
        func.count(AuditLog.id).label("count")
    ).filter(
        AuditLog.created_at >= start_time
    ).group_by(AuditLog.resource_type).all()

    return {
        "period_days": days,
        "total_operations": total_count,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_count / total_count * 100, 2) if total_count > 0 else 0,
        "by_action": {stat.action: stat.count for stat in action_stats},
        "by_resource": {stat.resource_type: stat.count for stat in resource_stats},
    }


async def cleanup_old_audit_logs(
    db: Session,
    days: int = 180,
) -> int:
    """清理旧的审计日志

    Args:
        db: 数据库会话
        days: 保留天数

    Returns:
        删除的记录数
    """
    cutoff = datetime.now() - timedelta(days=days)

    deleted = db.query(AuditLog).filter(
        AuditLog.created_at < cutoff
    ).delete()

    db.commit()
    logger.info(f"清理审计日志: 删除{deleted}条{days}天前的记录")

    return deleted


# ==================== 装饰器 ====================

def audit_log(
    action: str,
    resource_type: str,
    get_resource_id: Optional[callable] = None,
    get_resource_name: Optional[callable] = None,
    get_old_value: Optional[callable] = None,
    get_new_value: Optional[callable] = None,
):
    """审计日志装饰器

    用于自动记录API操作的审计日志

    Args:
        action: 操作类型
        resource_type: 资源类型
        get_resource_id: 获取资源ID的函数
        get_resource_name: 获取资源名称的函数
        get_old_value: 获取变更前值的函数
        get_new_value: 获取变更后值的函数

    Example:
        @router.post("/users/{user_id}")
        @audit_log(
            action=AuditAction.UPDATE,
            resource_type=AuditResource.USER,
            get_resource_id=lambda kwargs: kwargs.get("user_id"),
        )
        async def update_user(user_id: int, ...):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 获取db和request
            db = kwargs.get("db")
            request = kwargs.get("request") or kwargs.get("req")

            # 获取资源信息
            resource_id = get_resource_id(kwargs) if get_resource_id else None
            resource_name = get_resource_name(kwargs) if get_resource_name else None
            old_value = get_old_value(kwargs) if get_old_value else None

            try:
                # 执行原函数
                result = await func(*args, **kwargs)

                # 获取新值
                new_value = get_new_value(result) if get_new_value else None

                # 记录成功日志
                if db and request:
                    await log_user_action(
                        db=db,
                        request=request,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        resource_name=resource_name,
                        old_value=old_value,
                        new_value=new_value,
                        status="success",
                    )

                return result

            except Exception as e:
                # 记录失败日志
                if db and request:
                    await log_user_action(
                        db=db,
                        request=request,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        resource_name=resource_name,
                        status="failure",
                        error_message=str(e),
                    )
                raise

        return wrapper
    return decorator


# ==================== 便捷函数 ====================

class AuditLogger:
    """审计日志记录器类

    提供便捷的审计日志记录接口
    """

    def __init__(self, db: Session, request: Optional[Request] = None):
        self.db = db
        self.request = request

    async def log_create(
        self,
        resource_type: str,
        resource_id: str,
        resource_name: Optional[str] = None,
        new_value: Optional[Dict] = None,
    ) -> AuditLog:
        """记录创建操作"""
        return await log_user_action(
            db=self.db,
            request=self.request,
            action=AuditAction.CREATE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            new_value=new_value,
        ) if self.request else create_audit_log(
            db=self.db,
            action=AuditAction.CREATE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            new_value=new_value,
        )

    async def log_update(
        self,
        resource_type: str,
        resource_id: str,
        resource_name: Optional[str] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
    ) -> AuditLog:
        """记录更新操作"""
        return await log_user_action(
            db=self.db,
            request=self.request,
            action=AuditAction.UPDATE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_value=old_value,
            new_value=new_value,
        ) if self.request else create_audit_log(
            db=self.db,
            action=AuditAction.UPDATE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_value=old_value,
            new_value=new_value,
        )

    async def log_delete(
        self,
        resource_type: str,
        resource_id: str,
        resource_name: Optional[str] = None,
        old_value: Optional[Dict] = None,
    ) -> AuditLog:
        """记录删除操作"""
        return await log_user_action(
            db=self.db,
            request=self.request,
            action=AuditAction.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_value=old_value,
        ) if self.request else create_audit_log(
            db=self.db,
            action=AuditAction.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            old_value=old_value,
        )

    async def log_login(
        self,
        user_id: int,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """记录登录操作"""
        return await log_user_action(
            db=self.db,
            request=self.request,
            action=AuditAction.LOGIN,
            resource_type=AuditResource.USER,
            resource_id=str(user_id),
            status="success" if success else "failure",
            error_message=error_message,
        ) if self.request else create_audit_log(
            db=self.db,
            action=AuditAction.LOGIN,
            resource_type=AuditResource.USER,
            resource_id=str(user_id),
            user_id=user_id,
            status="success" if success else "failure",
            error_message=error_message,
        )

    async def log_payment(
        self,
        order_id: str,
        amount: float,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """记录支付操作"""
        return await log_user_action(
            db=self.db,
            request=self.request,
            action=AuditAction.PAY,
            resource_type=AuditResource.ORDER,
            resource_id=order_id,
            new_value={"amount": amount},
            status="success" if success else "failure",
            error_message=error_message,
        ) if self.request else create_audit_log(
            db=self.db,
            action=AuditAction.PAY,
            resource_type=AuditResource.ORDER,
            resource_id=order_id,
            new_value={"amount": amount},
            status="success" if success else "failure",
            error_message=error_message,
        )
