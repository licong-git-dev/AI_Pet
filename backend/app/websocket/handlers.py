"""
PetPal - WebSocket 路由处理器

处理 WebSocket 连接和消息：
- 连接认证
- 消息路由
- 心跳检测
"""
import json
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.database import get_db
from app.models.user import User
from app.models.social import Notification, Conversation, PrivateMessage
from app.config import settings

websocket_router = APIRouter()


# 获取全局连接管理器（延迟导入避免循环引用）
def get_manager():
    from app.websocket import manager
    return manager


async def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """从 token 获取用户"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            return None

        user = db.query(User).filter(User.id == user_id, User.status == 1).first()
        return user
    except JWTError:
        return None


@websocket_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket 主入口

    连接时需要在 URL 中提供 token 参数进行认证
    ws://host/ws?token=xxx

    消息格式：
    {
        "type": "message_type",
        "data": {...}
    }

    支持的消息类型：
    - ping: 心跳检测
    - chat: 发送聊天消息
    - typing: 正在输入指示
    - read: 已读回执
    - join_room: 加入房间
    - leave_room: 离开房间
    """
    manager = get_manager()

    # 验证 token
    user = await get_user_from_token(token, db)
    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # 建立连接
    connection = await manager.connect(websocket, user.id)

    try:
        # 发送连接成功消息
        await manager.send_personal(user.id, {
            "type": "connected",
            "data": {
                "user_id": user.id,
                "nickname": user.nickname,
                "server_time": datetime.now().isoformat()
            }
        })

        # 发送未读消息数
        unread_count = db.query(Notification).filter(
            Notification.user_id == user.id,
            Notification.is_read == 0
        ).count()

        await manager.send_personal(user.id, {
            "type": "unread_count",
            "data": {"count": unread_count}
        })

        # 消息处理循环
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=60.0  # 60秒超时
                )

                message = json.loads(data)
                msg_type = message.get("type")
                msg_data = message.get("data", {})

                # 处理不同类型的消息
                if msg_type == "ping":
                    await handle_ping(websocket, user.id, manager)

                elif msg_type == "chat":
                    await handle_chat(msg_data, user, db, manager)

                elif msg_type == "typing":
                    await handle_typing(msg_data, user.id, manager)

                elif msg_type == "read":
                    await handle_read(msg_data, user, db, manager)

                elif msg_type == "join_room":
                    room_id = msg_data.get("room_id")
                    if room_id:
                        await manager.join_room(user.id, room_id)
                        await manager.send_personal(user.id, {
                            "type": "room_joined",
                            "data": {"room_id": room_id}
                        })

                elif msg_type == "leave_room":
                    room_id = msg_data.get("room_id")
                    if room_id:
                        await manager.leave_room(user.id, room_id)
                        await manager.send_personal(user.id, {
                            "type": "room_left",
                            "data": {"room_id": room_id}
                        })

                elif msg_type == "get_online_friends":
                    await handle_get_online_friends(user.id, db, manager)

                else:
                    await manager.send_personal(user.id, {
                        "type": "error",
                        "data": {"message": f"Unknown message type: {msg_type}"}
                    })

            except asyncio.TimeoutError:
                # 发送心跳检测
                try:
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "data": {"timestamp": datetime.now().isoformat()}
                    }))
                except Exception:
                    break

            except json.JSONDecodeError:
                await manager.send_personal(user.id, {
                    "type": "error",
                    "data": {"message": "Invalid JSON format"}
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error for user {user.id}: {str(e)}")
    finally:
        await manager.disconnect(user.id, websocket)


async def handle_ping(websocket: WebSocket, user_id: int, manager):
    """处理心跳"""
    await manager.send_personal(user_id, {
        "type": "pong",
        "data": {"timestamp": datetime.now().isoformat()}
    })


async def handle_chat(data: dict, user: User, db: Session, manager):
    """处理聊天消息"""
    receiver_id = data.get("receiver_id")
    content = data.get("content", "").strip()
    image_url = data.get("image_url")

    if not receiver_id or (not content and not image_url):
        await manager.send_personal(user.id, {
            "type": "error",
            "data": {"message": "Invalid chat message"}
        })
        return

    # 检查接收者
    receiver = db.query(User).filter(User.id == receiver_id, User.status == 1).first()
    if not receiver:
        await manager.send_personal(user.id, {
            "type": "error",
            "data": {"message": "Receiver not found"}
        })
        return

    # 获取或创建会话
    conversation = db.query(Conversation).filter(
        ((Conversation.user1_id == user.id) & (Conversation.user2_id == receiver_id)) |
        ((Conversation.user1_id == receiver_id) & (Conversation.user2_id == user.id))
    ).first()

    if not conversation:
        conversation = Conversation(
            user1_id=min(user.id, receiver_id),
            user2_id=max(user.id, receiver_id)
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # 创建消息
    message = PrivateMessage(
        conversation_id=conversation.id,
        sender_id=user.id,
        receiver_id=receiver_id,
        content=content,
        image_url=image_url
    )
    db.add(message)

    # 更新会话
    conversation.last_message_id = message.id
    conversation.last_message_time = datetime.now()
    conversation.updated_at = datetime.now()

    # 更新未读数
    if conversation.user1_id == user.id:
        conversation.user2_unread += 1
    else:
        conversation.user1_unread += 1

    db.commit()
    db.refresh(message)

    # 构建消息数据
    message_data = {
        "id": message.id,
        "conversation_id": conversation.id,
        "sender_id": user.id,
        "sender_nickname": user.nickname,
        "sender_avatar": user.avatar_url,
        "receiver_id": receiver_id,
        "content": content,
        "image_url": image_url,
        "created_at": message.created_at.isoformat()
    }

    # 发送给发送者（确认）
    await manager.send_chat_message(user.id, {
        **message_data,
        "status": "sent"
    })

    # 发送给接收者
    if manager.is_online(receiver_id):
        await manager.send_chat_message(receiver_id, {
            **message_data,
            "status": "received"
        })


async def handle_typing(data: dict, user_id: int, manager):
    """处理正在输入指示"""
    receiver_id = data.get("receiver_id")
    is_typing = data.get("is_typing", False)

    if receiver_id and manager.is_online(receiver_id):
        await manager.send_typing_indicator(user_id, receiver_id, is_typing)


async def handle_read(data: dict, user: User, db: Session, manager):
    """处理已读回执"""
    message_ids = data.get("message_ids", [])
    conversation_id = data.get("conversation_id")

    if not message_ids and not conversation_id:
        return

    # 标记消息已读
    if message_ids:
        db.query(PrivateMessage).filter(
            PrivateMessage.id.in_(message_ids),
            PrivateMessage.receiver_id == user.id,
            PrivateMessage.is_read == 0
        ).update({"is_read": 1, "read_at": datetime.now()}, synchronize_session=False)

    # 更新会话未读数
    if conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if conversation:
            if conversation.user1_id == user.id:
                # 获取对方ID
                other_user_id = conversation.user2_id
                conversation.user1_unread = 0
            else:
                other_user_id = conversation.user1_id
                conversation.user2_unread = 0

            db.commit()

            # 发送已读回执给对方
            if message_ids and manager.is_online(other_user_id):
                await manager.send_read_receipt(user.id, other_user_id, message_ids)


async def handle_get_online_friends(user_id: int, db: Session, manager):
    """获取在线好友"""
    from app.models.social import Follow

    # 获取互相关注的用户（好友）
    following = db.query(Follow.following_id).filter(
        Follow.follower_id == user_id,
        Follow.status == 1
    ).subquery()

    friends = db.query(Follow.follower_id).filter(
        Follow.following_id == user_id,
        Follow.follower_id.in_(following),
        Follow.status == 1
    ).all()

    friend_ids = [f[0] for f in friends]

    # 检查在线状态
    online_friends = [fid for fid in friend_ids if manager.is_online(fid)]

    # 获取在线好友信息
    if online_friends:
        users = db.query(User).filter(User.id.in_(online_friends)).all()
        friend_list = [{
            "id": u.id,
            "nickname": u.nickname,
            "avatar_url": u.avatar_url
        } for u in users]
    else:
        friend_list = []

    await manager.send_personal(user_id, {
        "type": "online_friends",
        "data": {
            "friends": friend_list,
            "count": len(friend_list)
        }
    })


# ==================== WebSocket 工具路由 ====================

@websocket_router.get("/ws/stats", summary="WebSocket 连接统计")
async def get_ws_stats():
    """获取 WebSocket 连接统计信息（仅限管理员）"""
    manager = get_manager()
    return manager.get_stats()


@websocket_router.get("/ws/online/{user_id}", summary="检查用户在线状态")
async def check_user_online(user_id: int):
    """检查指定用户是否在线"""
    manager = get_manager()
    return {
        "user_id": user_id,
        "is_online": manager.is_online(user_id)
    }
