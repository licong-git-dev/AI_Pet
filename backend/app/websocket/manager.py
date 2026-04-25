"""
PetPal - WebSocket 连接管理器

管理所有 WebSocket 连接：
- 连接建立与断开
- 消息广播
- 用户在线状态
- 房间管理
"""
import json
import asyncio
from typing import Dict, Set, Optional, Any, List
from datetime import datetime
from fastapi import WebSocket
from dataclasses import dataclass, field


@dataclass
class UserConnection:
    """用户连接信息"""
    user_id: int
    websocket: WebSocket
    connected_at: datetime = field(default_factory=datetime.now)
    rooms: Set[str] = field(default_factory=set)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        # 用户连接映射: user_id -> List[UserConnection] (支持多设备)
        self._connections: Dict[int, List[UserConnection]] = {}
        # 房间成员映射: room_id -> Set[user_id]
        self._rooms: Dict[str, Set[int]] = {}
        # 锁，保证线程安全
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int) -> UserConnection:
        """建立连接"""
        await websocket.accept()

        connection = UserConnection(
            user_id=user_id,
            websocket=websocket
        )

        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []
            self._connections[user_id].append(connection)

        # 通知用户上线
        await self._broadcast_online_status(user_id, True)

        return connection

    async def disconnect(self, user_id: int, websocket: WebSocket):
        """断开连接"""
        async with self._lock:
            if user_id in self._connections:
                # 移除特定的连接
                self._connections[user_id] = [
                    conn for conn in self._connections[user_id]
                    if conn.websocket != websocket
                ]

                # 如果用户没有其他连接，清理
                if not self._connections[user_id]:
                    del self._connections[user_id]
                    # 从所有房间移除
                    for room_id in list(self._rooms.keys()):
                        self._rooms[room_id].discard(user_id)
                        if not self._rooms[room_id]:
                            del self._rooms[room_id]

                    # 通知用户下线
                    await self._broadcast_online_status(user_id, False)

    def is_online(self, user_id: int) -> bool:
        """检查用户是否在线"""
        return user_id in self._connections and len(self._connections[user_id]) > 0

    def get_online_users(self) -> List[int]:
        """获取所有在线用户"""
        return list(self._connections.keys())

    def get_online_count(self) -> int:
        """获取在线用户数"""
        return len(self._connections)

    async def join_room(self, user_id: int, room_id: str):
        """加入房间"""
        async with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = set()
            self._rooms[room_id].add(user_id)

            # 更新用户连接的房间信息
            if user_id in self._connections:
                for conn in self._connections[user_id]:
                    conn.rooms.add(room_id)

    async def leave_room(self, user_id: int, room_id: str):
        """离开房间"""
        async with self._lock:
            if room_id in self._rooms:
                self._rooms[room_id].discard(user_id)
                if not self._rooms[room_id]:
                    del self._rooms[room_id]

            # 更新用户连接的房间信息
            if user_id in self._connections:
                for conn in self._connections[user_id]:
                    conn.rooms.discard(room_id)

    def get_room_members(self, room_id: str) -> Set[int]:
        """获取房间成员"""
        return self._rooms.get(room_id, set()).copy()

    async def send_personal(self, user_id: int, message: dict):
        """发送个人消息"""
        if user_id in self._connections:
            message_str = json.dumps(message, ensure_ascii=False, default=str)
            disconnected = []

            for conn in self._connections[user_id]:
                try:
                    await conn.websocket.send_text(message_str)
                except Exception:
                    disconnected.append(conn.websocket)

            # 清理断开的连接
            for ws in disconnected:
                await self.disconnect(user_id, ws)

    async def send_to_users(self, user_ids: List[int], message: dict):
        """发送消息给多个用户"""
        tasks = [self.send_personal(uid, message) for uid in user_ids if uid in self._connections]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_room(self, room_id: str, message: dict, exclude_user: int = None):
        """向房间广播消息"""
        if room_id not in self._rooms:
            return

        user_ids = [uid for uid in self._rooms[room_id] if uid != exclude_user]
        await self.send_to_users(user_ids, message)

    async def broadcast_all(self, message: dict, exclude_user: int = None):
        """向所有在线用户广播"""
        user_ids = [uid for uid in self._connections.keys() if uid != exclude_user]
        await self.send_to_users(user_ids, message)

    async def _broadcast_online_status(self, user_id: int, is_online: bool):
        """广播用户在线状态变化"""
        # 这里可以实现通知好友用户上下线的逻辑
        # 暂时不做全局广播，避免性能问题
        pass

    # ==================== 业务消息发送方法 ====================

    async def send_notification(self, user_id: int, notification: dict):
        """发送通知消息"""
        message = {
            "type": "notification",
            "data": notification,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal(user_id, message)

    async def send_chat_message(self, user_id: int, chat_message: dict):
        """发送聊天消息"""
        message = {
            "type": "chat",
            "data": chat_message,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal(user_id, message)

    async def send_system_message(self, user_id: int, content: str):
        """发送系统消息"""
        message = {
            "type": "system",
            "data": {"content": content},
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal(user_id, message)

    async def broadcast_system_notice(self, content: str, title: str = "系统通知"):
        """广播系统公告"""
        message = {
            "type": "system_notice",
            "data": {
                "title": title,
                "content": content
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_all(message)

    async def send_activity_update(self, activity_id: int, update_type: str, data: dict):
        """发送活动更新通知"""
        room_id = f"activity:{activity_id}"
        message = {
            "type": "activity_update",
            "data": {
                "activity_id": activity_id,
                "update_type": update_type,  # joined, left, started, ended, cancelled
                **data
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_to_room(room_id, message)

    async def send_order_update(self, user_id: int, order_id: int, status: str, data: dict = None):
        """发送订单状态更新"""
        message = {
            "type": "order_update",
            "data": {
                "order_id": order_id,
                "status": status,
                **(data or {})
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal(user_id, message)

    async def send_typing_indicator(self, from_user_id: int, to_user_id: int, is_typing: bool):
        """发送正在输入指示器"""
        message = {
            "type": "typing",
            "data": {
                "user_id": from_user_id,
                "is_typing": is_typing
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal(to_user_id, message)

    async def send_read_receipt(self, from_user_id: int, to_user_id: int, message_ids: List[int]):
        """发送已读回执"""
        message = {
            "type": "read_receipt",
            "data": {
                "user_id": from_user_id,
                "message_ids": message_ids
            },
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal(to_user_id, message)

    # ==================== 统计方法 ====================

    def get_stats(self) -> dict:
        """获取连接统计信息"""
        total_connections = sum(len(conns) for conns in self._connections.values())
        return {
            "online_users": len(self._connections),
            "total_connections": total_connections,
            "active_rooms": len(self._rooms),
            "room_stats": {
                room_id: len(members)
                for room_id, members in self._rooms.items()
            }
        }
