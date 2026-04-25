"""
PetPal - 抽象渲染器基类

每个具体 driver 需实现：
- supported_capabilities()
- send(event): 把事件分发到具体设备
- alive(): 心跳/在线探活
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Set
from app.services.avatar_render.protocol import AvatarStateEvent


class AvatarRenderer(ABC):
    """渲染器接口"""

    #: 设备类型，与 device_bindings.device_type 取值对齐
    device_type: str = "abstract"

    def __init__(self, *, device_id: str, capabilities: Optional[Dict[str, bool]] = None) -> None:
        self.device_id = device_id
        self.capabilities = capabilities or {}

    @abstractmethod
    def supported_capabilities(self) -> Set[str]:
        """返回该 driver 支持的能力集合，例如 {speech, animation, emotion}。"""

    @abstractmethod
    async def send(self, event: AvatarStateEvent) -> bool:
        """把事件投递到对应设备；成功返回 True。"""

    async def alive(self) -> bool:
        """心跳/探活，默认 True。具体 driver 可重写为发起 ping。"""
        return True

    def can_handle(self, event: AvatarStateEvent) -> bool:
        """根据 event.type 与自身能力判断是否处理；不能处理时静默丢弃。"""
        cap = self.supported_capabilities()
        if event.type == "speech":
            return "speech" in cap
        if event.type == "animation":
            return "animation" in cap
        if event.type in ("emotion", "gaze", "idle", "wake", "sleep", "system"):
            return event.type in cap or "emotion" in cap
        return True
