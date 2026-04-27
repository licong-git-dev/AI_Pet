"""
PetPal - 社交模型 (关注、消息、活动)
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, Float, func
from app.database import Base


class Follow(Base):
    """关注关系表"""
    __tablename__ = "follows"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="关注ID")
    follower_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="粉丝ID")
    following_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="被关注者ID")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )


class Message(Base):
    """私信消息表"""
    __tablename__ = "messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="消息ID")
    sender_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="发送者ID")
    receiver_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="接收者ID")
    conversation_id = Column(String(50), nullable=False, index=True, comment="会话ID")

    message_type = Column(String(20), default="text", comment="消息类型: text文本 image图片 video视频")
    content = Column(Text, nullable=True, comment="消息内容")
    media_url = Column(String(500), nullable=True, comment="媒体URL")

    is_read = Column(Integer, default=0, comment="是否已读: 0未读 1已读")
    read_at = Column(DateTime, nullable=True, comment="阅读时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


# 兼容别名：websocket 处理器使用 PrivateMessage 这个旧名字
PrivateMessage = Message


class Activity(Base):
    """线下活动表"""
    __tablename__ = "activities"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="活动ID")
    creator_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="创建者ID")

    title = Column(String(200), nullable=False, comment="活动标题")
    description = Column(Text, nullable=True, comment="活动描述")
    cover_image = Column(String(500), nullable=True, comment="封面图")
    images = Column(Text, nullable=True, comment="活动图片(JSON)")

    # 活动类型
    activity_type = Column(String(50), nullable=False, comment="活动类型: walk遛狗 party聚会 competition比赛 charity公益 other其他")

    # 时间地点
    start_time = Column(DateTime, nullable=False, comment="开始时间")
    end_time = Column(DateTime, nullable=True, comment="结束时间")
    location_name = Column(String(200), nullable=True, comment="地点名称")
    location_address = Column(String(500), nullable=True, comment="详细地址")
    latitude = Column(String(20), nullable=True, comment="纬度")
    longitude = Column(String(20), nullable=True, comment="经度")

    # 参与信息
    max_participants = Column(Integer, default=0, comment="最大参与人数(0为不限)")
    current_participants = Column(Integer, default=0, comment="当前参与人数")
    fee = Column(Float, default=0, comment="参与费用")

    # 宠物要求
    pet_types = Column(Text, nullable=True, comment="允许的宠物类型(JSON)")
    pet_required = Column(Integer, default=0, comment="是否必须带宠物: 0否 1是")

    # 状态
    status = Column(String(20), default="upcoming", comment="状态: upcoming即将开始 ongoing进行中 completed已结束 cancelled已取消")

    views_count = Column(Integer, default=0, comment="浏览数")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "creator_id": self.creator_id,
            "title": self.title,
            "description": self.description,
            "cover_image": self.cover_image,
            "activity_type": self.activity_type,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location_name": self.location_name,
            "location_address": self.location_address,
            "max_participants": self.max_participants,
            "current_participants": self.current_participants,
            "fee": self.fee,
            "status": self.status,
            "views_count": self.views_count
        }


class ActivityParticipant(Base):
    """活动参与者表"""
    __tablename__ = "activity_participants"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="参与ID")
    activity_id = Column(BigInteger, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True, comment="活动ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="SET NULL"), nullable=True, comment="宠物ID")

    status = Column(String(20), default="registered", comment="状态: registered已报名 checked_in已签到 cancelled已取消")
    check_in_time = Column(DateTime, nullable=True, comment="签到时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class Notification(Base):
    """系统通知表"""
    __tablename__ = "notifications"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="通知ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="接收用户ID")
    sender_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="触发用户ID")

    # 通知类型
    notify_type = Column(String(30), nullable=False, index=True, comment="类型: like点赞 comment评论 follow关注 mention提及 reply回复 system系统 order订单 points积分")

    # 关联内容
    target_type = Column(String(30), nullable=True, comment="目标类型: post帖子 comment评论 order订单 product商品")
    target_id = Column(BigInteger, nullable=True, index=True, comment="目标ID")

    # 内容
    title = Column(String(200), nullable=True, comment="通知标题")
    content = Column(String(500), nullable=True, comment="通知内容")
    extra_data = Column(Text, nullable=True, comment="额外数据(JSON)")

    # 状态
    is_read = Column(Integer, default=0, comment="是否已读: 0未读 1已读")
    read_at = Column(DateTime, nullable=True, comment="阅读时间")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        import json
        return {
            "id": self.id,
            "user_id": self.user_id,
            "sender_id": self.sender_id,
            "notify_type": self.notify_type,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "title": self.title,
            "content": self.content,
            "extra_data": json.loads(self.extra_data) if self.extra_data else None,
            "is_read": bool(self.is_read),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Conversation(Base):
    """会话表（私信会话列表）"""
    __tablename__ = "conversations"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="会话ID")
    conversation_id = Column(String(50), unique=True, nullable=False, index=True, comment="会话标识")
    user1_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户1")
    user2_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户2")

    last_message_id = Column(BigInteger, nullable=True, comment="最后一条消息ID")
    last_message_content = Column(String(500), nullable=True, comment="最后一条消息内容")
    last_message_time = Column(DateTime, nullable=True, comment="最后消息时间")
    last_message_type = Column(String(20), default="text", comment="最后消息类型")

    # 各用户未读数
    user1_unread = Column(Integer, default=0, comment="用户1未读数")
    user2_unread = Column(Integer, default=0, comment="用户2未读数")

    # 各用户是否删除会话
    user1_deleted = Column(Integer, default=0, comment="用户1是否删除")
    user2_deleted = Column(Integer, default=0, comment="用户2是否删除")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self, current_user_id: int):
        """转换为字典"""
        # 确定对方信息
        other_user_id = self.user2_id if self.user1_id == current_user_id else self.user1_id
        unread_count = self.user1_unread if self.user1_id == current_user_id else self.user2_unread

        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "other_user_id": other_user_id,
            "last_message": self.last_message_content,
            "last_message_type": self.last_message_type,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
            "unread_count": unread_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
