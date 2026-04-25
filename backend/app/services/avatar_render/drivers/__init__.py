"""
PetPal - 渲染器具体实现

- web.py: 通过 WebSocket 推送给前端 Live2D / 3D 渲染器
- hologram.py: 通过 MQTT 推送给桌面雾屏 / Looking Glass（v0.1 mock）
- desktop_pet.py: 通过 BLE relay / MQTT 推送给桌面机器人 / 投影玩具（v0.1 mock）
"""
from app.services.avatar_render.drivers.web import WebRenderer
from app.services.avatar_render.drivers.hologram import HologramRenderer
from app.services.avatar_render.drivers.desktop_pet import DesktopPetRenderer

__all__ = ["WebRenderer", "HologramRenderer", "DesktopPetRenderer"]
