"""
Hologram 渲染器：通过 MQTT 推送给桌面雾屏 / Looking Glass / 投影玩具。

v0.1 占位实现：把事件写入 logger，并支持注入自定义 publisher 以便联调。
后续接 paho-mqtt / EMQX，topic 设计：petpal/avatar/{device_id}/state
"""
from typing import Optional, Set, Callable, Awaitable
from loguru import logger

from app.services.avatar_render.base import AvatarRenderer
from app.services.avatar_render.protocol import AvatarStateEvent


class HologramRenderer(AvatarRenderer):
    """全息渲染器（桌面雾屏 / Looking Glass）"""

    device_type = "hologram"

    def __init__(
        self,
        *,
        device_id: str,
        capabilities: Optional[dict] = None,
        publisher: Optional[Callable[[str, dict], Awaitable[bool]]] = None,
    ) -> None:
        super().__init__(device_id=device_id, capabilities=capabilities)
        self._publisher = publisher  # async (topic, payload) -> bool

    def supported_capabilities(self) -> Set[str]:
        return {"speech", "animation", "emotion", "gaze", "idle", "system"}

    async def send(self, event: AvatarStateEvent) -> bool:
        topic = f"petpal/avatar/{self.device_id}/state"
        payload = event.to_wire()
        if self._publisher is not None:
            try:
                ok = await self._publisher(topic, payload)
                logger.debug(f"[hologram] publish topic={topic} ok={ok}")
                return ok
            except Exception as e:
                logger.warning(f"[hologram] publish failed: {e}")
                return False
        # mock 路径：仅记录
        logger.info(f"[hologram] mock publish topic={topic} type={event.type} avatar={event.avatar_id}")
        return True
