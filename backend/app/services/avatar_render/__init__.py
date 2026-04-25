"""
PetPal - 分身渲染适配层

让宠物分身能在多种设备上呈现：网页 Live2D、桌面雾屏全息、桌宠机器人、AR 等。

公共抽象：
- protocol.AvatarStateEvent: 跨终端统一事件协议（ASP v0.1）
- base.AvatarRenderer: 抽象渲染器
- orchestrator.AvatarRenderOrchestrator: 根据用户绑定的设备 fan-out

drivers/ 下放各终端的具体实现。
"""
from app.services.avatar_render.protocol import (
    AvatarStateEvent,
    AvatarEventType,
    AvatarEmotion,
    SpeechPayload,
    AnimationPayload,
)
from app.services.avatar_render.base import AvatarRenderer
from app.services.avatar_render.orchestrator import AvatarRenderOrchestrator, get_orchestrator

__all__ = [
    "AvatarStateEvent",
    "AvatarEventType",
    "AvatarEmotion",
    "SpeechPayload",
    "AnimationPayload",
    "AvatarRenderer",
    "AvatarRenderOrchestrator",
    "get_orchestrator",
]
