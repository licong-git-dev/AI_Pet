"""
PetPal - 主人画像 Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field


class DailyRhythm(BaseModel):
    wake_time: Optional[str] = None       # "08:00"
    sleep_time: Optional[str] = None      # "23:30"
    peak_active_hours: Optional[List[int]] = None  # [21, 22, 23]
    weekend_pattern: Optional[str] = None  # "晚起约 10:00"


class EmotionalBaseline(BaseModel):
    dominant_moods: Optional[List[str]] = None
    stress_triggers: Optional[List[str]] = None
    comfort_topics: Optional[List[str]] = None


class Relationships(BaseModel):
    family_members: Optional[List[Dict[str, Any]]] = None  # [{name, relation}]
    work_role: Optional[str] = None
    hobbies: Optional[List[str]] = None


class Communication(BaseModel):
    tone_preference: Optional[str] = None   # gentle / playful / concise
    length: Optional[str] = None            # short / medium / long
    emoji_usage: Optional[str] = None       # rare / moderate / heavy
    taboos: Optional[List[str]] = None


class PetAttachment(BaseModel):
    nicknames: Optional[List[str]] = None
    special_dates: Optional[List[Dict[str, Any]]] = None  # [{name, date}]
    ritual_moments: Optional[List[str]] = None


class OwnerProfileResponse(BaseModel):
    user_id: int
    daily_rhythm: Optional[Dict[str, Any]] = None
    emotional_baseline: Optional[Dict[str, Any]] = None
    relationships: Optional[Dict[str, Any]] = None
    communication: Optional[Dict[str, Any]] = None
    pet_attachment: Optional[Dict[str, Any]] = None
    confidence_score: float = 0.0
    signal_count: int = 0
    last_built_at: Optional[datetime] = None
    is_visible_to_avatar: bool = True
    is_learning_paused: bool = False
    pause_until: Optional[datetime] = None

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    """主人手动修正画像（可只传想改的字段）"""
    daily_rhythm: Optional[DailyRhythm] = None
    emotional_baseline: Optional[EmotionalBaseline] = None
    relationships: Optional[Relationships] = None
    communication: Optional[Communication] = None
    pet_attachment: Optional[PetAttachment] = None
    is_visible_to_avatar: Optional[bool] = None


class PauseLearningRequest(BaseModel):
    days: int = Field(7, ge=1, le=90)


class RecordSignalRequest(BaseModel):
    """显式上报信号（一般由前端触发，如打开宠物详情页）"""
    signal_type: str
    payload: Optional[Dict[str, Any]] = None
    text_excerpt: Optional[str] = Field(None, max_length=255)
