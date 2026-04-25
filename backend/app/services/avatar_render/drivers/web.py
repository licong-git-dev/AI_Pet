"""
Web 渲染器：通过现有 WebSocket 通道推送 ASP 事件到前端 Live2D / 3D。

复用 app/websocket/manager.py 的 send_personal() 方法。
"""
from typing import Set
from loguru import logger

from app.services.avatar_render.base import AvatarRenderer
from app.services.avatar_render.protocol import AvatarStateEvent


class WebRenderer(AvatarRenderer):
    """Web / Mobile 端 WebSocket 渲染器"""

    device_type = "web"

    def supported_capabilities(self) -> Set[str]:
        return {"speech", "animation", "emotion", "gaze", "idle", "wake", "sleep", "system"}

    async def send(self, event: AvatarStateEvent) -> bool:
        try:
            from app.websocket.manager import manager  # 延迟导入避免循环
        except Exception:
            from app.websocket import manager as _mgr_mod  # 兜底
            manager = getattr(_mgr_mod, "manager", None)
        if manager is None:
            logger.warning("[web_renderer] websocket manager unavailable")
            return False

        message = {
            "channel": "avatar_render",
            "asp_version": event.asp_version,
            "event": event.to_wire(),
        }
        try:
            await manager.send_personal(event.user_id, message)
            return True
        except Exception as e:
            logger.warning(f"[web_renderer] send failed user={event.user_id}: {e}")
            return False
