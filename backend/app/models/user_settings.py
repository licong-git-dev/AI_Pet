"""
PetPal - 用户设置模型

包含：
- 用户设置（隐私、通知偏好）
- 用户黑名单
- 用户收货地址
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, func
from app.database import Base


class UserSettings(Base):
    """用户设置表"""
    __tablename__ = "user_settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="设置ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True, comment="用户ID")

    # 隐私设置
    profile_visibility = Column(String(20), default="public", comment="个人主页可见性: public公开 followers仅粉丝 private私密")
    show_online_status = Column(Integer, default=1, comment="显示在线状态: 0否 1是")
    show_pet_list = Column(Integer, default=1, comment="显示宠物列表: 0否 1是")
    allow_stranger_message = Column(Integer, default=1, comment="允许陌生人私信: 0否 1是")
    allow_comment = Column(Integer, default=1, comment="允许评论: 0否 1是")
    show_location = Column(Integer, default=0, comment="显示位置: 0否 1是")

    # 通知设置
    notify_like = Column(Integer, default=1, comment="点赞通知: 0否 1是")
    notify_comment = Column(Integer, default=1, comment="评论通知: 0否 1是")
    notify_follow = Column(Integer, default=1, comment="关注通知: 0否 1是")
    notify_message = Column(Integer, default=1, comment="私信通知: 0否 1是")
    notify_system = Column(Integer, default=1, comment="系统通知: 0否 1是")
    notify_activity = Column(Integer, default=1, comment="活动通知: 0否 1是")
    notify_health_reminder = Column(Integer, default=1, comment="健康提醒: 0否 1是")

    # 推送设置
    push_enabled = Column(Integer, default=1, comment="启用推送: 0否 1是")
    push_quiet_start = Column(String(5), nullable=True, comment="免打扰开始时间(HH:MM)")
    push_quiet_end = Column(String(5), nullable=True, comment="免打扰结束时间(HH:MM)")

    # 其他设置
    language = Column(String(10), default="zh-CN", comment="语言")
    theme = Column(String(20), default="light", comment="主题: light亮色 dark暗色 auto自动")
    font_size = Column(String(10), default="medium", comment="字体大小: small small medium large")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "profile_visibility": self.profile_visibility,
            "show_online_status": bool(self.show_online_status),
            "show_pet_list": bool(self.show_pet_list),
            "allow_stranger_message": bool(self.allow_stranger_message),
            "allow_comment": bool(self.allow_comment),
            "show_location": bool(self.show_location),
            "notifications": {
                "like": bool(self.notify_like),
                "comment": bool(self.notify_comment),
                "follow": bool(self.notify_follow),
                "message": bool(self.notify_message),
                "system": bool(self.notify_system),
                "activity": bool(self.notify_activity),
                "health_reminder": bool(self.notify_health_reminder)
            },
            "push": {
                "enabled": bool(self.push_enabled),
                "quiet_start": self.push_quiet_start,
                "quiet_end": self.push_quiet_end
            },
            "display": {
                "language": self.language,
                "theme": self.theme,
                "font_size": self.font_size
            }
        }


class UserBlacklist(Base):
    """用户黑名单表"""
    __tablename__ = "user_blacklist"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    blocked_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="被拉黑用户ID")
    reason = Column(String(200), nullable=True, comment="拉黑原因")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )


class UserAddress(Base):
    """用户收货地址表"""
    __tablename__ = "user_addresses"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="地址ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    receiver_name = Column(String(50), nullable=False, comment="收货人")
    receiver_phone = Column(String(20), nullable=False, comment="联系电话")
    province = Column(String(50), nullable=False, comment="省份")
    city = Column(String(50), nullable=False, comment="城市")
    district = Column(String(50), nullable=False, comment="区/县")
    detail_address = Column(String(200), nullable=False, comment="详细地址")
    postal_code = Column(String(10), nullable=True, comment="邮编")

    tag = Column(String(20), nullable=True, comment="标签: home家 company公司")
    is_default = Column(Integer, default=0, comment="是否默认: 0否 1是")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "receiver_name": self.receiver_name,
            "receiver_phone": self.receiver_phone,
            "province": self.province,
            "city": self.city,
            "district": self.district,
            "detail_address": self.detail_address,
            "postal_code": self.postal_code,
            "full_address": f"{self.province}{self.city}{self.district}{self.detail_address}",
            "tag": self.tag,
            "is_default": bool(self.is_default)
        }


class UserFeedback(Base):
    """用户反馈表"""
    __tablename__ = "user_feedbacks"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="反馈ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="用户ID")

    feedback_type = Column(String(50), nullable=False, comment="反馈类型: bug问题反馈 suggestion建议 complaint投诉 other其他")
    content = Column(Text, nullable=False, comment="反馈内容")
    images = Column(Text, nullable=True, comment="反馈图片(JSON数组)")
    contact = Column(String(100), nullable=True, comment="联系方式")

    status = Column(String(20), default="pending", comment="状态: pending待处理 processing处理中 resolved已解决 closed已关闭")
    reply = Column(Text, nullable=True, comment="回复内容")
    replied_at = Column(DateTime, nullable=True, comment="回复时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        import json
        return {
            "id": self.id,
            "feedback_type": self.feedback_type,
            "content": self.content,
            "images": json.loads(self.images) if self.images else [],
            "status": self.status,
            "reply": self.reply,
            "replied_at": self.replied_at.isoformat() if self.replied_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class UserReport(Base):
    """用户举报表"""
    __tablename__ = "user_reports"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="举报ID")
    reporter_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="举报人ID")

    # 举报对象
    target_type = Column(String(20), nullable=False, comment="举报类型: user用户 post帖子 comment评论 message私信")
    target_id = Column(BigInteger, nullable=False, comment="举报对象ID")

    reason = Column(String(50), nullable=False, comment="举报原因: spam垃圾广告 abuse辱骂 porn色情 fraud诈骗 other其他")
    description = Column(Text, nullable=True, comment="详细描述")
    evidence_images = Column(Text, nullable=True, comment="证据图片(JSON数组)")

    status = Column(String(20), default="pending", comment="状态: pending待处理 processing处理中 valid有效 invalid无效")
    handle_result = Column(Text, nullable=True, comment="处理结果")
    handled_at = Column(DateTime, nullable=True, comment="处理时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "reason": self.reason,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
