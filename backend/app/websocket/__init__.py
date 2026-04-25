"""
PetPal - WebSocket 实时通信模块

提供实时通信功能：
- 实时消息推送
- 在线状态管理
- 私聊消息
- 系统通知
"""
from app.websocket.manager import ConnectionManager
from app.websocket.handlers import websocket_router

manager = ConnectionManager()

__all__ = ["manager", "websocket_router", "ConnectionManager"]
