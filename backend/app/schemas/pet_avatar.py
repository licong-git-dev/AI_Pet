"""
PetPal - 宠物数字分身Schema
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


# ==================== 数字分身 ====================

class CreateAvatarRequest(BaseModel):
    """创建数字分身请求"""
    pet_id: int = Field(..., description="宠物ID")
    photo_url: Optional[str] = Field(None, description="照片URL(不传则使用宠物头像)")
    image_base64: Optional[str] = Field(None, max_length=10_000_000, description="照片base64(直接上传，最大约7.5MB)")
    speaking_style: Literal["cute", "sassy", "lazy", "energetic", "gentle"] = Field("cute", description="说话风格")

    @field_validator('photo_url')
    @classmethod
    def validate_photo_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.startswith(('http://', 'https://')):
                raise ValueError('photo_url 必须是 http/https 开头的 URL')
        return v


class UpdateAvatarRequest(BaseModel):
    """更新数字分身请求"""
    speaking_style: Optional[Literal["cute", "sassy", "lazy", "energetic", "gentle"]] = Field(None, description="说话风格")
    persona: Optional[Dict[str, Any]] = Field(None, description="人设配置")


class AvatarResponse(BaseModel):
    """数字分身响应"""
    id: int
    pet_id: int
    appearance_desc: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None
    speaking_style: str
    chat_count: int = 0
    sticker_count: int = 0
    is_active: bool = True
    created_at: Optional[str] = None


# ==================== 宠物对话 ====================

class AvatarChatRequest(BaseModel):
    """宠物对话请求"""
    message: str = Field(..., min_length=1, max_length=500, description="用户消息")
    chat_id: Optional[int] = Field(None, description="会话ID(不传则创建新会话)")


class ChatMessageResponse(BaseModel):
    """对话消息响应"""
    reply: str = Field(..., description="宠物回复")
    chat_id: int = Field(..., description="会话ID")
    message_id: int = Field(..., description="消息ID")


class ChatListItem(BaseModel):
    """会话列表项"""
    id: int
    title: Optional[str] = None
    message_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ChatDetailResponse(BaseModel):
    """会话详情响应"""
    id: int
    title: Optional[str] = None
    message_count: int = 0
    messages: List[Dict[str, Any]] = []
    created_at: Optional[str] = None


# ==================== 表情包 ====================

class GenerateStickerRequest(BaseModel):
    """生成表情包请求"""
    photo_url: Optional[str] = Field(None, description="原始照片URL(不传则使用宠物头像)")
    emotion: Literal["happy", "sleepy", "angry", "hungry", "love", "surprised", "sad", "cool"] = Field(..., description="表情类型")

    @field_validator('photo_url')
    @classmethod
    def validate_photo_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith(('http://', 'https://')):
            raise ValueError('photo_url 必须是 http/https 开头的 URL')
        return v


class StickerResponse(BaseModel):
    """表情包响应"""
    id: int
    pet_id: int
    emotion: str
    sticker_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    status: str = "pending"
    share_count: int = 0
    created_at: Optional[str] = None


class StickerEmotionItem(BaseModel):
    """表情类型项"""
    key: str
    name: str
    emoji: str
    description: str


# ==================== 性格分析 ====================

class GeneratePersonalityRequest(BaseModel):
    """生成性格分析请求"""
    photo_url: Optional[str] = Field(None, description="照片URL(不传则使用宠物头像)")

    @field_validator('photo_url')
    @classmethod
    def validate_photo_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.startswith(('http://', 'https://')):
            raise ValueError('photo_url 必须是 http/https 开头的 URL')
        return v


class PersonalityProfileResponse(BaseModel):
    """性格档案响应"""
    id: int
    pet_id: int
    energy_level: Optional[int] = None
    affection_level: Optional[int] = None
    curiosity_level: Optional[int] = None
    foodie_level: Optional[int] = None
    intelligence_level: Optional[int] = None
    mischief_level: Optional[int] = None
    analysis_text: Optional[str] = None
    personality_tags: Optional[List[str]] = None
    fun_description: Optional[str] = None
    spirit_animal: Optional[str] = None
    motto: Optional[str] = None
    photo_url: Optional[str] = None
    persona_type: Optional[str] = None
    persona_type_name: Optional[str] = None
    persona_type_emoji: Optional[str] = None
    persona_type_color: Optional[str] = None
    persona_type_slogan: Optional[str] = None
    created_at: Optional[str] = None
