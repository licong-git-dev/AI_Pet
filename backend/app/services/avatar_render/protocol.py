"""
PetPal - Avatar State Protocol (ASP) v0.1

跨终端统一的分身状态事件协议。
所有 driver 都消费同一份事件，自行决定如何呈现。

参考：docs/PRODUCT_DESIGN.md §3.4
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


# ==================== 类型枚举 ====================

AvatarEventType = Literal[
    "speech",     # 说话（含文本和可选音频）
    "emotion",    # 情绪切换
    "animation",  # 播放动作
    "gaze",       # 注视方向
    "idle",       # 进入待机
    "wake",       # 被唤醒
    "sleep",      # 进入休眠
    "system",     # 系统事件（被绑定/解绑/状态同步）
]

AvatarEmotion = Literal[
    "happy", "sleepy", "curious", "loving", "sad",
    "angry", "surprised", "neutral", "confused", "proud",
]


# ==================== Payload 子结构 ====================

class SpeechPayload(BaseModel):
    text: str
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    voice_style: Optional[str] = None  # 关联 PetAvatar.speaking_style


class AnimationPayload(BaseModel):
    name: str = Field(..., description="动作名，如 wag_tail / blink / sit")
    loop: bool = False
    duration_ms: Optional[int] = None


class GazePayload(BaseModel):
    target: Optional[str] = None  # "owner" / "screen" / "left" / "right" ...
    yaw: Optional[float] = None    # 水平角度
    pitch: Optional[float] = None  # 俯仰角度


class PosturePayload(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    facing: Optional[str] = None  # "left" / "right" / "front"


# ==================== 主事件 ====================

class AvatarStateEvent(BaseModel):
    """分身状态事件 - ASP 的核心数据结构"""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    avatar_id: int
    user_id: int
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: AvatarEventType

    emotion: Optional[AvatarEmotion] = None
    intensity: float = Field(0.5, ge=0.0, le=1.0)

    speech: Optional[SpeechPayload] = None
    animation: Optional[AnimationPayload] = None
    gaze: Optional[GazePayload] = None
    posture: Optional[PosturePayload] = None

    # 自由扩展字段，driver 各取所需
    extra: Optional[Dict[str, Any]] = None
    ttl_ms: int = Field(5000, description="事件有效期，driver 可丢弃过期事件")

    # 协议版本
    asp_version: str = "0.1"

    def to_wire(self) -> dict:
        """统一的线上序列化（保证字段顺序与日期序列化一致）。"""
        return self.model_dump(mode="json", exclude_none=True)
