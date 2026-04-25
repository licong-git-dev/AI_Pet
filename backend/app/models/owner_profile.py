"""
PetPal - 主人画像模型

OwnerProfile: 一个用户对应一行，存储维度化画像（节律、情感、关系、沟通偏好、宠物依恋）
OwnerSignal: 时序原子信号，作为画像的"原料"

参考：docs/PRODUCT_DESIGN.md §2
"""
from sqlalchemy import (
    Column, BigInteger, String, Integer, DateTime, Text, ForeignKey,
    Float, func, Boolean, JSON, text, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ==================== 信号类型枚举 ====================

SIGNAL_TYPES = (
    "login",            # 登录事件
    "chat_start",       # 进入对话
    "chat_end",         # 离开对话
    "message",          # 消息（含长度、时间）
    "sentiment",        # 消息情感分析结果
    "explicit_input",   # 主人主动填写问卷 / 设置
    "app_event",        # 其它行为事件（看了某条记忆、给某宠物点赞）
    "milestone",        # 主人标记的纪念日
)


class OwnerProfile(Base):
    """主人画像主表（一个用户对应一行）"""
    __tablename__ = "owner_profiles"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, comment="用户ID")

    # 五个维度（全部 JSON，便于演进）
    daily_rhythm = Column(JSON, nullable=True, comment="生活节律 {wake, sleep, peak_hours[], weekend_pattern}")
    emotional_baseline = Column(JSON, nullable=True, comment="情感基线 {dominant_moods[], stress_triggers[], comfort_topics[]}")
    relationships = Column(JSON, nullable=True, comment="关系网络 {family[], work_role, hobbies[]}")
    communication = Column(JSON, nullable=True, comment="沟通偏好 {tone, length, emoji_usage, taboos[]}")
    pet_attachment = Column(JSON, nullable=True, comment="宠物依恋 {nicknames[], special_dates[], ritual_moments[]}")

    confidence_score = Column(Float, server_default=text('0.0'), comment="置信度 0-1")
    signal_count = Column(Integer, server_default=text('0'), comment="构建该画像所用的信号数")

    last_built_at = Column(DateTime, nullable=True, comment="最近一次构建时间")
    is_visible_to_avatar = Column(Boolean, server_default=text('1'), comment="分身是否可读取")
    is_learning_paused = Column(Boolean, server_default=text('0'), comment="是否暂停学习")
    pause_until = Column(DateTime, nullable=True, comment="暂停到何时")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "daily_rhythm": self.daily_rhythm,
            "emotional_baseline": self.emotional_baseline,
            "relationships": self.relationships,
            "communication": self.communication,
            "pet_attachment": self.pet_attachment,
            "confidence_score": self.confidence_score,
            "signal_count": self.signal_count,
            "last_built_at": self.last_built_at.isoformat() if self.last_built_at else None,
            "is_visible_to_avatar": self.is_visible_to_avatar,
            "is_learning_paused": self.is_learning_paused,
            "pause_until": self.pause_until.isoformat() if self.pause_until else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class OwnerSignal(Base):
    """主人原子信号流"""
    __tablename__ = "owner_signals"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    signal_type = Column(String(20), nullable=False, index=True, comment="信号类型枚举")
    payload = Column(JSON, nullable=True, comment="信号数据 JSON")

    # 常用展开字段（便于过滤聚合，避免每条都拆 JSON）
    sentiment_score = Column(Float, nullable=True, comment="-1 ~ 1")
    sentiment_label = Column(String(20), nullable=True, comment="happy/sad/...")
    text_excerpt = Column(String(255), nullable=True, comment="原文摘录（脱敏）")

    recorded_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_owner_signals_user_type_time", "user_id", "signal_type", "recorded_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "signal_type": self.signal_type,
            "payload": self.payload,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "text_excerpt": self.text_excerpt,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }
