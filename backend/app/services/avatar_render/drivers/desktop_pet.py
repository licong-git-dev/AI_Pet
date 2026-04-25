"""
Desktop Pet 渲染器：BLE relay / MQTT 推送给桌面机器人 / 投影玩具。

v0.1 占位实现。真实硬件接入时改写 send() 即可，外部接口不变。
ASP 事件会被压缩成简化指令包（只保留低带宽设备能用的字段）：

    {
      "v": 1,
      "t": "speech | emotion | anim | gaze | idle",
      "emo": "happy",
      "txt": "...",          # 仅 speech
      "anim": "wag_tail",    # 仅 animation
      "ttl": 5000
    }
"""
from typing import Optional, Set, Callable, Awaitable
from loguru import logger

from app.services.avatar_render.base import AvatarRenderer
from app.services.avatar_render.protocol import AvatarStateEvent


class DesktopPetRenderer(AvatarRenderer):
    """桌宠/玩具渲染器"""

    device_type = "desktop_pet"

    def __init__(
        self,
        *,
        device_id: str,
        capabilities: Optional[dict] = None,
        publisher: Optional[Callable[[str, dict], Awaitable[bool]]] = None,
    ) -> None:
        super().__init__(device_id=device_id, capabilities=capabilities)
        self._publisher = publisher

    def supported_capabilities(self) -> Set[str]:
        # 资源受限设备：通常没有 speech audio，文字交给云端 TTS 后再下发
        caps = {"emotion", "animation", "idle"}
        # 设备声明的 capabilities 可裁剪
        if (self.capabilities or {}).get("speech"):
            caps.add("speech")
        return caps

    def _compress(self, event: AvatarStateEvent) -> dict:
        type_map = {"animation": "anim"}
        out = {
            "v": 1,
            "t": type_map.get(event.type, event.type),
            "ttl": event.ttl_ms,
        }
        if event.emotion:
            out["emo"] = event.emotion
        if event.speech and event.speech.text:
            out["txt"] = event.speech.text[:240]
        if event.animation and event.animation.name:
            out["anim"] = event.animation.name
        return out

    async def send(self, event: AvatarStateEvent) -> bool:
        topic = f"petpal/desktop_pet/{self.device_id}/cmd"
        payload = self._compress(event)
        if self._publisher is not None:
            try:
                return await self._publisher(topic, payload)
            except Exception as e:
                logger.warning(f"[desktop_pet] publish failed: {e}")
                return False
        logger.info(f"[desktop_pet] mock send device={self.device_id} payload={payload}")
        return True
