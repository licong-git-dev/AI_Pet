"""
PetPal - 长期记忆 Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


MemoryType = Literal["episodic", "semantic", "preference", "event"]
MemoryEmotion = Literal[
    "happy", "loving", "proud",
    "neutral",
    "sad", "anxious", "worried", "lonely",
    "angry",
]


class CreateMemoryRequest(BaseModel):
    """主人手动添加一条记忆"""
    pet_avatar_id: int
    memory_type: MemoryType = "episodic"
    content: str = Field(..., min_length=1, max_length=2000)
    summary: Optional[str] = Field(None, max_length=255)
    importance: int = Field(5, ge=0, le=10)
    emotion: Optional[MemoryEmotion] = None
    emotion_intensity: Optional[float] = Field(None, ge=0.0, le=1.0)
    happened_at: Optional[datetime] = None


class UpdateMemoryRequest(BaseModel):
    """更新记忆（修正/置顶/归档）"""
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    summary: Optional[str] = Field(None, max_length=255)
    importance: Optional[int] = Field(None, ge=0, le=10)
    emotion: Optional[MemoryEmotion] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None


class RetrieveMemoryRequest(BaseModel):
    """对话时检索记忆"""
    pet_avatar_id: int
    query: str = Field(..., min_length=1, max_length=500, description="当前对话的查询文本")
    top_k: int = Field(5, ge=1, le=20)
    include_archived: bool = False


class MemoryResponse(BaseModel):
    id: int
    pet_avatar_id: int
    memory_type: str
    content: str
    summary: Optional[str] = None
    importance: int
    emotion: Optional[str] = None
    emotion_intensity: Optional[float] = None
    source: str
    happened_at: Optional[datetime] = None
    last_recalled_at: Optional[datetime] = None
    recall_count: int = 0
    effective_strength: float = 1.0
    is_archived: bool = False
    is_pinned: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MemoryGardenStats(BaseModel):
    """记忆花园整体统计 — 用于 UI 可视化"""
    total: int
    by_type: dict
    by_emotion: dict
    pinned_count: int
    archived_count: int
    oldest_memory_at: Optional[datetime] = None
    newest_memory_at: Optional[datetime] = None
    top_themes: List[str] = []


class MemoryDigestResponse(BaseModel):
    id: int
    period_type: str
    period_start: datetime
    period_end: datetime
    summary: str
    key_themes: Optional[list] = None
    dominant_emotion: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
