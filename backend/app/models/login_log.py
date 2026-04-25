"""
PetPal - 登录日志模型

记录用户登录历史，用于安全审计和异地登录检测
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Index
from sqlalchemy.orm import relationship

from app.database import Base


class LoginLog(Base):
    """登录日志模型"""

    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="用户ID(登录失败时可能为空)")

    # 登录信息
    phone = Column(String(20), nullable=True, comment="登录手机号")
    login_type = Column(String(20), default="sms", comment="登录方式: sms/password/wechat/apple")

    # 设备信息
    login_ip = Column(String(50), nullable=False, comment="登录IP地址")
    login_location = Column(String(100), nullable=True, comment="登录地点(从IP解析)")
    login_device = Column(String(200), nullable=True, comment="登录设备(从User-Agent解析)")
    device_type = Column(String(20), nullable=True, comment="设备类型: mobile/tablet/pc/other")
    browser = Column(String(50), nullable=True, comment="浏览器")
    os = Column(String(50), nullable=True, comment="操作系统")
    user_agent = Column(Text, nullable=True, comment="完整User-Agent")

    # 登录状态
    login_status = Column(Boolean, default=True, comment="登录是否成功")
    failure_reason = Column(String(200), nullable=True, comment="登录失败原因")

    # 安全标记
    is_abnormal = Column(Boolean, default=False, comment="是否异常登录(异地)")
    risk_level = Column(String(20), default="low", comment="风险等级: low/medium/high")

    # 时间戳
    login_time = Column(DateTime, default=datetime.now, comment="登录时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关系
    user = relationship("User", backref="login_logs")

    # 索引
    __table_args__ = (
        Index("idx_login_log_user_id", "user_id"),
        Index("idx_login_log_phone", "phone"),
        Index("idx_login_log_ip", "login_ip"),
        Index("idx_login_log_time", "login_time"),
        Index("idx_login_log_status", "login_status"),
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "login_type": self.login_type,
            "login_ip": self.login_ip,
            "login_location": self.login_location,
            "login_device": self.login_device,
            "device_type": self.device_type,
            "browser": self.browser,
            "os": self.os,
            "login_status": self.login_status,
            "failure_reason": self.failure_reason,
            "is_abnormal": self.is_abnormal,
            "risk_level": self.risk_level,
            "login_time": self.login_time.isoformat() if self.login_time else None,
        }

    def __repr__(self):
        return f"<LoginLog(id={self.id}, user_id={self.user_id}, ip={self.login_ip}, status={self.login_status})>"
