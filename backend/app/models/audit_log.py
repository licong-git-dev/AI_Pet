"""
PetPal - 审计日志模型

记录系统中的敏感操作，用于安全审计和问题追踪
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    """审计日志模型

    记录用户的敏感操作历史
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # 操作用户
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="操作用户ID")

    # 操作信息
    action = Column(String(50), nullable=False, comment="操作类型: create/update/delete/login/logout/pay等")
    action_desc = Column(String(200), nullable=True, comment="操作描述")

    # 资源信息
    resource_type = Column(String(50), nullable=False, comment="资源类型: user/pet/post/order等")
    resource_id = Column(String(50), nullable=True, comment="资源ID")
    resource_name = Column(String(100), nullable=True, comment="资源名称(便于展示)")

    # 变更内容
    old_value = Column(JSON, nullable=True, comment="变更前的值(JSON)")
    new_value = Column(JSON, nullable=True, comment="变更后的值(JSON)")
    changes = Column(JSON, nullable=True, comment="具体变更字段(JSON)")

    # 请求信息
    request_ip = Column(String(50), nullable=True, comment="请求IP")
    request_location = Column(String(100), nullable=True, comment="请求地点")
    user_agent = Column(Text, nullable=True, comment="User-Agent")
    request_id = Column(String(50), nullable=True, comment="请求ID(用于追踪)")

    # 结果
    status = Column(String(20), default="success", comment="操作结果: success/failure")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 时间戳
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    user = relationship("User", backref="audit_logs")

    # 索引
    __table_args__ = (
        Index("idx_audit_log_user_id", "user_id"),
        Index("idx_audit_log_action", "action"),
        Index("idx_audit_log_resource", "resource_type", "resource_id"),
        Index("idx_audit_log_time", "created_at"),
        Index("idx_audit_log_request_id", "request_id"),
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "action_desc": self.action_desc,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changes": self.changes,
            "request_ip": self.request_ip,
            "request_location": self.request_location,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, resource={self.resource_type}:{self.resource_id})>"


# 审计日志操作类型常量
class AuditAction:
    """审计操作类型"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    PROFILE_UPDATE = "profile_update"
    PAY = "pay"
    REFUND = "refund"
    EXPORT = "export"
    IMPORT = "import"
    APPROVE = "approve"
    REJECT = "reject"
    ENABLE = "enable"
    DISABLE = "disable"


# 审计资源类型常量
class AuditResource:
    """审计资源类型"""
    USER = "user"
    PET = "pet"
    POST = "post"
    COMMENT = "comment"
    ORDER = "order"
    PRODUCT = "product"
    HEALTH_RECORD = "health_record"
    DIAGNOSIS = "diagnosis"
    ACTIVITY = "activity"
    MESSAGE = "message"
    POINTS = "points"
    SETTINGS = "settings"
