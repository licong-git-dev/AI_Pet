"""
PetPal - 渲染编排器

职责：
- 接收一个 AvatarStateEvent，根据用户的 device_bindings 把事件 fan-out 到所有 driver
- 兜底使用 WebRenderer（即使没显式绑定，前端 WebSocket 在线就能收到）
- 离线设备会被静默跳过（status != online）

driver 实例缓存策略：每个 device_id 一份。MQTT/BLE publisher 注入由生产环境组装。
"""
from typing import Dict, List, Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.services.avatar_render.protocol import AvatarStateEvent
from app.services.avatar_render.base import AvatarRenderer
from app.services.avatar_render.drivers import (
    WebRenderer, HologramRenderer, DesktopPetRenderer,
)


class AvatarRenderOrchestrator:
    """全局唯一编排器（进程内单例）"""

    def __init__(self) -> None:
        # device_id -> renderer
        self._renderers: Dict[str, AvatarRenderer] = {}
        # publisher 注入点：生产环境注入真正的 MQTT publisher
        self._mqtt_publisher = None

    def configure_mqtt_publisher(self, publisher) -> None:
        self._mqtt_publisher = publisher

    # -------- 内部：按设备类型构造 renderer --------
    def _build_renderer(self, device_type: str, device_id: str, capabilities: Optional[dict]) -> Optional[AvatarRenderer]:
        if device_type in ("web", "mobile"):
            return WebRenderer(device_id=device_id, capabilities=capabilities)
        if device_type == "hologram":
            return HologramRenderer(
                device_id=device_id,
                capabilities=capabilities,
                publisher=self._mqtt_publisher,
            )
        if device_type == "desktop_pet":
            return DesktopPetRenderer(
                device_id=device_id,
                capabilities=capabilities,
                publisher=self._mqtt_publisher,
            )
        logger.warning(f"[orchestrator] unsupported device_type={device_type}")
        return None

    def _renderer_for(self, device_type: str, device_id: str, capabilities: Optional[dict]) -> Optional[AvatarRenderer]:
        key = f"{device_type}:{device_id}"
        r = self._renderers.get(key)
        if r is None:
            r = self._build_renderer(device_type, device_id, capabilities)
            if r:
                self._renderers[key] = r
        return r

    # -------- 主入口 --------
    async def broadcast(self, db: Session, event: AvatarStateEvent) -> Dict[str, int]:
        """
        把事件投递给该用户绑定的所有在线设备。

        Returns:
            {"sent": int, "failed": int, "skipped": int}
        """
        # 延迟导入避免循环
        from app.models.device import DeviceBinding

        bindings: List[DeviceBinding] = (
            db.query(DeviceBinding)
            .filter(
                DeviceBinding.user_id == event.user_id,
                DeviceBinding.status == "online",
            )
            .all()
        )

        sent, failed, skipped = 0, 0, 0
        delivered_to_web = False

        for b in bindings:
            r = self._renderer_for(b.device_type, b.device_id, b.capabilities)
            if r is None:
                skipped += 1
                continue
            if not r.can_handle(event):
                skipped += 1
                continue
            try:
                ok = await r.send(event)
                if ok:
                    sent += 1
                    if b.device_type in ("web", "mobile"):
                        delivered_to_web = True
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"[orchestrator] driver={b.device_type} send error: {e}")
                failed += 1

        # 兜底：即使无 web 绑定也尝试推送 WebSocket（用户当前会话）
        if not delivered_to_web:
            web = self._renderer_for("web", f"session-{event.user_id}", None)
            if web and web.can_handle(event):
                try:
                    if await web.send(event):
                        sent += 1
                except Exception:
                    failed += 1

        logger.info(f"[orchestrator] avatar={event.avatar_id} type={event.type} sent={sent} failed={failed} skipped={skipped}")
        return {"sent": sent, "failed": failed, "skipped": skipped}


_orchestrator: Optional[AvatarRenderOrchestrator] = None


def get_orchestrator() -> AvatarRenderOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AvatarRenderOrchestrator()
    return _orchestrator
