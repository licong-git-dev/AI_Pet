"""
PetPal - 长期记忆模型

实现宠物分身的"情景 / 语义 / 偏好"三层记忆体系，
支持重要度、情绪强度、艾宾浩斯式遗忘曲线、检索召回统计。

参考：docs/PRODUCT_DESIGN.md §1
"""
from sqlalchemy import (
    Column, BigInteger, String, Integer, SmallInteger, DateTime, Text,
    ForeignKey, Float, func, Boolean, JSON, text, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ==================== 枚举常量 ====================

MEMORY_TYPES = ("episodic", "semantic", "preference", "event")
"""
- episodic: 一次性发生的具体事件（"今天主人加班到 11 点"）
- semantic: 由若干 episodic 周期归纳出的一般性事实（"主人通常 23:30 后睡"）
- preference: 主人/宠物的稳定偏好（"主人喜欢叫我豆包"）
- event: 重要节日 / 纪念日（领养日、生日）
"""

MEMORY_EMOTIONS = (
    "happy", "loving", "proud",      # 正向
    "neutral",                       # 中性
    "sad", "anxious", "worried", "lonely",  # 负向
    "angry",                          # 强烈负向
)

MEMORY_SOURCES = (
    "conversation",     # 从对话中由 LLM 抽取
    "observation",      # 系统观察（登录时间、活跃模式）
    "user_input",       # 主人手动添加
    "weekly_digest",    # 周期总结生成的 semantic
    "milestone",        # 里程碑事件（生日、领养日）
)


class PetMemory(Base):
    """宠物分身长期记忆表"""
    __tablename__ = "pet_memories"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记忆ID")
    pet_avatar_id = Column(BigInteger, ForeignKey("pet_avatars.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属分身ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属用户ID")

    memory_type = Column(String(20), nullable=False, index=True, comment="记忆类型: episodic/semantic/preference/event")
    content = Column(Text, nullable=False, comment="记忆原文（用于喂给 LLM）")
    summary = Column(String(255), nullable=True, comment="一句话摘要（用于列表展示）")

    importance = Column(SmallInteger, nullable=False, server_default=text('5'), comment="重要度 0-10")
    emotion = Column(String(20), nullable=True, comment="情绪标签")
    emotion_intensity = Column(Float, nullable=True, comment="情绪强度 0-1")

    source = Column(String(20), nullable=False, server_default="conversation", comment="来源: conversation/observation/user_input/weekly_digest/milestone")
    source_ref = Column(String(100), nullable=True, comment="来源引用，如对话消息ID")

    happened_at = Column(DateTime, nullable=True, comment="事件实际发生时间")

    # 检索 / 衰减
    embedding_vector_id = Column(String(64), nullable=True, comment="向量ID，指向 Milvus / pgvector，v1 可空")
    last_recalled_at = Column(DateTime, nullable=True, comment="最近一次被检索召回时间")
    recall_count = Column(Integer, server_default=text('0'), comment="召回次数")
    effective_strength = Column(Float, server_default=text('1.0'), comment="缓存的衰减强度")

    is_archived = Column(Boolean, server_default=text('0'), comment="是否归档（弱化但保留）")
    is_pinned = Column(Boolean, server_default=text('0'), comment="是否被主人置顶（永不衰减）")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        Index("ix_pet_memories_avatar_type", "pet_avatar_id", "memory_type"),
        Index("ix_pet_memories_user_archived", "user_id", "is_archived"),
        Index("ix_pet_memories_strength", "effective_strength"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "pet_avatar_id": self.pet_avatar_id,
            "user_id": self.user_id,
            "memory_type": self.memory_type,
            "content": self.content,
            "summary": self.summary,
            "importance": self.importance,
            "emotion": self.emotion,
            "emotion_intensity": self.emotion_intensity,
            "source": self.source,
            "source_ref": self.source_ref,
            "happened_at": self.happened_at.isoformat() if self.happened_at else None,
            "last_recalled_at": self.last_recalled_at.isoformat() if self.last_recalled_at else None,
            "recall_count": self.recall_count,
            "effective_strength": self.effective_strength,
            "is_archived": self.is_archived,
            "is_pinned": self.is_pinned,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MemoryDigest(Base):
    """周期性记忆摘要（"这周主人状态偏疲惫"等元记忆）"""
    __tablename__ = "memory_digests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    pet_avatar_id = Column(BigInteger, ForeignKey("pet_avatars.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    period_type = Column(String(10), nullable=False, comment="周期: daily/weekly/monthly")
    period_start = Column(DateTime, nullable=False, comment="周期开始时间")
    period_end = Column(DateTime, nullable=False, comment="周期结束时间")

    summary = Column(Text, nullable=False, comment="LLM 生成的摘要")
    key_themes = Column(JSON, nullable=True, comment="关键主题数组")
    dominant_emotion = Column(String(20), nullable=True, comment="主导情绪")
    sourced_memory_ids = Column(JSON, nullable=True, comment="基于哪些 memory_id 生成")

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_memory_digests_avatar_period", "pet_avatar_id", "period_type", "period_start"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "pet_avatar_id": self.pet_avatar_id,
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "summary": self.summary,
            "key_themes": self.key_themes,
            "dominant_emotion": self.dominant_emotion,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
