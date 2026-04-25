"""
PetPal - 宠物数字分身模型

包含：数字分身、对话会话、对话消息、表情包、性格档案
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, Float, func, Boolean, JSON, text
from sqlalchemy.orm import relationship
from app.database import Base


class PetAvatar(Base):
    """宠物数字分身表"""
    __tablename__ = "pet_avatars"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="分身ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True, comment="宠物ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    # AI分析的外貌描述
    appearance_desc = Column(Text, nullable=True, comment="AI分析的外貌描述")
    # 数字分身人设 (JSON: first_person_intro, suggested_traits, catchphrases)
    persona = Column(JSON, nullable=True, comment="数字分身人设JSON")
    # 说话风格: cute可爱/sassy傲娇/lazy慵懒/energetic活泼/gentle温柔
    speaking_style = Column(String(20), nullable=False, server_default="cute", comment="说话风格")

    # 统计
    chat_count = Column(Integer, server_default=text('0'), comment="聊天次数")
    sticker_count = Column(Integer, server_default=text('0'), comment="生成表情包次数")

    is_active = Column(Boolean, server_default=text('1'), comment="是否激活")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    chats = relationship("PetAvatarChat", back_populates="avatar", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "user_id": self.user_id,
            "appearance_desc": self.appearance_desc,
            "persona": self.persona,
            "speaking_style": self.speaking_style,
            "chat_count": self.chat_count,
            "sticker_count": self.sticker_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PetAvatarChat(Base):
    """宠物对话会话表"""
    __tablename__ = "pet_avatar_chats"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="会话ID")
    avatar_id = Column(BigInteger, ForeignKey("pet_avatars.id", ondelete="CASCADE"), nullable=False, index=True, comment="分身ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    title = Column(String(200), nullable=True, comment="会话标题")
    message_count = Column(Integer, server_default=text('0'), comment="消息数量")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    avatar = relationship("PetAvatar", back_populates="chats")
    messages = relationship("PetAvatarMessage", back_populates="chat", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "avatar_id": self.avatar_id,
            "user_id": self.user_id,
            "title": self.title,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PetAvatarMessage(Base):
    """宠物对话消息表"""
    __tablename__ = "pet_avatar_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="消息ID")
    chat_id = Column(BigInteger, ForeignKey("pet_avatar_chats.id", ondelete="CASCADE"), nullable=False, index=True, comment="会话ID")

    role = Column(String(20), nullable=False, comment="角色: user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    chat = relationship("PetAvatarChat", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PetSticker(Base):
    """宠物表情包表"""
    __tablename__ = "pet_stickers"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="表情包ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True, comment="宠物ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    # 生成参数
    source_photo_url = Column(String(500), nullable=False, comment="原始照片URL")
    emotion = Column(String(50), nullable=False, comment="表情类型: happy/sleepy/angry/hungry/love/surprised/sad/cool")
    prompt_used = Column(Text, nullable=True, comment="生成所用的prompt")

    # 生成结果
    sticker_url = Column(String(500), nullable=True, comment="表情包URL")
    thumbnail_url = Column(String(500), nullable=True, comment="缩略图URL")

    # 异步任务
    task_id = Column(String(100), nullable=True, comment="DashScope任务ID")
    status = Column(String(20), server_default="pending", index=True, comment="状态: pending/generating/completed/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")

    # 统计
    share_count = Column(Integer, server_default=text('0'), comment="分享次数")
    save_count = Column(Integer, server_default=text('0'), comment="保存次数")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "user_id": self.user_id,
            "source_photo_url": self.source_photo_url,
            "emotion": self.emotion,
            "sticker_url": self.sticker_url,
            "thumbnail_url": self.thumbnail_url,
            "status": self.status,
            "share_count": self.share_count,
            "save_count": self.save_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PersonalityProfile(Base):
    """宠物性格分析档案表"""
    __tablename__ = "personality_profiles"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="档案ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True, comment="宠物ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    # 分析来源
    photo_url = Column(String(500), nullable=True, comment="分析使用的照片URL")

    # 性格维度 (0-100)
    energy_level = Column(Integer, nullable=True, comment="活泼度")
    affection_level = Column(Integer, nullable=True, comment="粘人度")
    curiosity_level = Column(Integer, nullable=True, comment="好奇心")
    foodie_level = Column(Integer, nullable=True, comment="吃货指数")
    intelligence_level = Column(Integer, nullable=True, comment="智商指数")
    mischief_level = Column(Integer, nullable=True, comment="调皮指数")

    # AI分析结果
    analysis_text = Column(Text, nullable=True, comment="AI分析文本")
    personality_tags = Column(JSON, nullable=True, comment="性格标签JSON数组")
    fun_description = Column(Text, nullable=True, comment="趣味性格描述")
    spirit_animal = Column(String(50), nullable=True, comment="灵魂动物")
    motto = Column(String(200), nullable=True, comment="人生座右铭")

    # PetSona 类型
    persona_type = Column(String(30), nullable=True, comment="PetSona类型ID")
    persona_type_name = Column(String(50), nullable=True, comment="PetSona类型名")
    persona_type_emoji = Column(String(20), nullable=True, comment="PetSona类型emoji")
    persona_type_color = Column(String(10), nullable=True, comment="PetSona类型颜色")
    persona_type_slogan = Column(String(100), nullable=True, comment="PetSona类型标语")

    # AI模型
    ai_model = Column(String(50), server_default="qwen-vl-max", comment="使用的AI模型")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "user_id": self.user_id,
            "photo_url": self.photo_url,
            "energy_level": self.energy_level,
            "affection_level": self.affection_level,
            "curiosity_level": self.curiosity_level,
            "foodie_level": self.foodie_level,
            "intelligence_level": self.intelligence_level,
            "mischief_level": self.mischief_level,
            "analysis_text": self.analysis_text,
            "personality_tags": self.personality_tags,
            "fun_description": self.fun_description,
            "spirit_animal": self.spirit_animal,
            "motto": self.motto,
            "persona_type": self.persona_type,
            "persona_type_name": self.persona_type_name,
            "persona_type_emoji": self.persona_type_emoji,
            "persona_type_color": self.persona_type_color,
            "persona_type_slogan": self.persona_type_slogan,
            "ai_model": self.ai_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
