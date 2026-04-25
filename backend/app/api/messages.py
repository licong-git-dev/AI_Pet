"""
PetPal - 消息通知API

提供完整的消息功能：
- 系统通知（点赞、评论、关注等）
- 私信会话
- 消息管理
- 未读统计
"""
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_, func

from app.database import get_db
from app.models.user import User
from app.models.social import Message, Notification, Conversation
from app.models.user_settings import UserBlacklist, UserSettings
from app.utils.deps import get_current_user
from app.utils.response import success, page_response

router = APIRouter()


# ==================== 通知相关 ====================

@router.get("/notifications", summary="获取通知列表")
async def get_notifications(
    notify_type: Optional[str] = Query(None, description="类型: like/comment/follow/reply/system/order/points"),
    is_read: Optional[int] = Query(None, description="是否已读: 0未读 1已读"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取通知列表"""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if notify_type:
        query = query.filter(Notification.notify_type == notify_type)

    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)

    query = query.order_by(desc(Notification.created_at))

    total = query.count()
    notifications = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取发送者信息
    sender_ids = [n.sender_id for n in notifications if n.sender_id]
    senders = {}
    if sender_ids:
        users = db.query(User).filter(User.id.in_(sender_ids)).all()
        senders = {u.id: {"id": u.id, "nickname": u.nickname, "avatar_url": u.avatar_url} for u in users}

    result = []
    for n in notifications:
        n_dict = n.to_dict()
        n_dict["sender"] = senders.get(n.sender_id) if n.sender_id else None
        result.append(n_dict)

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/notifications/unread-count", summary="获取未读通知数")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取各类通知未读数"""
    # 分类统计
    counts = db.query(
        Notification.notify_type,
        func.count(Notification.id)
    ).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == 0
    ).group_by(Notification.notify_type).all()

    type_counts = {t: c for t, c in counts}

    # 互动类通知（点赞、评论、关注、回复）
    interaction_types = ["like", "comment", "follow", "reply", "mention"]
    interaction_count = sum(type_counts.get(t, 0) for t in interaction_types)

    # 系统通知
    system_count = type_counts.get("system", 0)

    # 订单通知
    order_count = type_counts.get("order", 0)

    # 总计
    total_count = sum(type_counts.values())

    return success(data={
        "total": total_count,
        "interaction": interaction_count,
        "system": system_count,
        "order": order_count,
        "detail": type_counts
    })


@router.post("/notifications/read", summary="标记通知已读")
async def mark_notifications_read(
    notification_ids: Optional[List[int]] = Body(None, description="通知ID列表，不传则全部标为已读"),
    notify_type: Optional[str] = Body(None, description="按类型标记已读"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """标记通知为已读"""
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == 0
    )

    if notification_ids:
        query = query.filter(Notification.id.in_(notification_ids))

    if notify_type:
        query = query.filter(Notification.notify_type == notify_type)

    now = datetime.now()
    updated = query.update({
        "is_read": 1,
        "read_at": now
    }, synchronize_session=False)

    db.commit()

    return success(message=f"已标记{updated}条通知为已读")


@router.delete("/notifications", summary="删除通知")
async def delete_notifications(
    notification_ids: List[int] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除通知"""
    deleted = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.id.in_(notification_ids)
    ).delete(synchronize_session=False)

    db.commit()

    return success(message=f"已删除{deleted}条通知")


@router.delete("/notifications/all", summary="清空通知")
async def clear_notifications(
    notify_type: Optional[str] = Query(None, description="按类型清空"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """清空通知"""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if notify_type:
        query = query.filter(Notification.notify_type == notify_type)

    deleted = query.delete(synchronize_session=False)
    db.commit()

    return success(message=f"已清空{deleted}条通知")


# ==================== 私信会话 ====================

def _get_conversation_id(user1_id: int, user2_id: int) -> str:
    """生成会话ID（保证两个用户之间只有一个会话）"""
    ids = sorted([user1_id, user2_id])
    return f"{ids[0]}_{ids[1]}"


@router.get("/conversations", summary="获取会话列表")
async def get_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取私信会话列表"""
    query = db.query(Conversation).filter(
        or_(
            and_(Conversation.user1_id == current_user.id, Conversation.user1_deleted == 0),
            and_(Conversation.user2_id == current_user.id, Conversation.user2_deleted == 0)
        )
    ).order_by(desc(Conversation.last_message_time))

    total = query.count()
    conversations = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取对方用户信息
    other_user_ids = []
    for conv in conversations:
        other_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
        other_user_ids.append(other_id)

    users = {}
    if other_user_ids:
        user_list = db.query(User).filter(User.id.in_(other_user_ids)).all()
        users = {u.id: {"id": u.id, "nickname": u.nickname, "avatar_url": u.avatar_url} for u in user_list}

    result = []
    for conv in conversations:
        conv_dict = conv.to_dict(current_user.id)
        conv_dict["other_user"] = users.get(conv_dict["other_user_id"])
        result.append(conv_dict)

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/conversations/{user_id}", summary="获取与某用户的会话")
async def get_conversation_with_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取与某用户的会话信息"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能与自己建立会话")

    conversation_id = _get_conversation_id(current_user.id, user_id)

    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()

    if not conversation:
        # 返回空会话信息
        other_user = db.query(User).filter(User.id == user_id).first()
        if not other_user:
            raise HTTPException(status_code=404, detail="用户不存在")

        return success(data={
            "conversation_id": conversation_id,
            "other_user": {
                "id": other_user.id,
                "nickname": other_user.nickname,
                "avatar_url": other_user.avatar_url
            },
            "last_message": None,
            "unread_count": 0,
            "is_new": True
        })

    other_user = db.query(User).filter(User.id == user_id).first()

    conv_dict = conversation.to_dict(current_user.id)
    conv_dict["other_user"] = {
        "id": other_user.id,
        "nickname": other_user.nickname,
        "avatar_url": other_user.avatar_url
    } if other_user else None
    conv_dict["is_new"] = False

    return success(data=conv_dict)


@router.delete("/conversations/{conversation_id}", summary="删除会话")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除会话（软删除，对方仍可见）"""
    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 标记当前用户已删除
    if conversation.user1_id == current_user.id:
        conversation.user1_deleted = 1
        conversation.user1_unread = 0
    elif conversation.user2_id == current_user.id:
        conversation.user2_deleted = 1
        conversation.user2_unread = 0
    else:
        raise HTTPException(status_code=403, detail="无权操作此会话")

    db.commit()

    return success(message="会话已删除")


# ==================== 私信消息 ====================

@router.get("/messages/{conversation_id}", summary="获取会话消息")
async def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取会话中的消息列表"""
    # 验证会话权限
    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()

    if conversation:
        if conversation.user1_id != current_user.id and conversation.user2_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权查看此会话")

    # 获取消息
    query = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(desc(Message.created_at))

    total = query.count()
    messages = query.offset((page - 1) * page_size).limit(page_size).all()

    # 标记为已读
    if conversation:
        if conversation.user1_id == current_user.id:
            conversation.user1_unread = 0
        else:
            conversation.user2_unread = 0

        db.query(Message).filter(
            Message.conversation_id == conversation_id,
            Message.receiver_id == current_user.id,
            Message.is_read == 0
        ).update({"is_read": 1, "read_at": datetime.now()}, synchronize_session=False)

        db.commit()

    # 获取用户信息
    user_ids = set()
    for msg in messages:
        user_ids.add(msg.sender_id)
        user_ids.add(msg.receiver_id)

    users = {}
    if user_ids:
        user_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users = {u.id: {"id": u.id, "nickname": u.nickname, "avatar_url": u.avatar_url} for u in user_list}

    result = []
    for msg in messages:
        result.append({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "receiver_id": msg.receiver_id,
            "message_type": msg.message_type,
            "content": msg.content,
            "media_url": msg.media_url,
            "is_read": bool(msg.is_read),
            "is_mine": msg.sender_id == current_user.id,
            "sender": users.get(msg.sender_id),
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        })

    # 反转顺序（最新的在后面）
    result.reverse()

    return success(data={
        "list": result,
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.post("/messages", summary="发送私信")
async def send_message(
    receiver_id: int = Body(..., gt=0),
    content: str = Body(..., min_length=1, max_length=2000),
    message_type: str = Body("text"),
    media_url: Optional[str] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """发送私信"""
    if receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能给自己发消息")

    # 检查接收者是否存在
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否被拉黑
    is_blocked = db.query(UserBlacklist).filter(
        UserBlacklist.user_id == receiver_id,
        UserBlacklist.blocked_user_id == current_user.id
    ).first()
    if is_blocked:
        raise HTTPException(status_code=403, detail="对方已将您拉黑")

    # 检查对方隐私设置
    settings = db.query(UserSettings).filter(UserSettings.user_id == receiver_id).first()
    if settings and not settings.allow_stranger_message:
        # 检查是否互相关注
        from app.models.social import Follow
        mutual = db.query(Follow).filter(
            Follow.follower_id == current_user.id,
            Follow.following_id == receiver_id
        ).first() and db.query(Follow).filter(
            Follow.follower_id == receiver_id,
            Follow.following_id == current_user.id
        ).first()
        if not mutual:
            raise HTTPException(status_code=403, detail="对方仅允许好友私信")

    # 获取或创建会话
    conversation_id = _get_conversation_id(current_user.id, receiver_id)

    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()

    if not conversation:
        # 创建新会话
        user1_id = min(current_user.id, receiver_id)
        user2_id = max(current_user.id, receiver_id)

        conversation = Conversation(
            conversation_id=conversation_id,
            user1_id=user1_id,
            user2_id=user2_id
        )
        db.add(conversation)
        db.flush()

    # 创建消息
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        conversation_id=conversation_id,
        message_type=message_type,
        content=content,
        media_url=media_url
    )
    db.add(message)
    db.flush()

    # 更新会话
    conversation.last_message_id = message.id
    conversation.last_message_content = content[:100] if message_type == "text" else f"[{message_type}]"
    conversation.last_message_time = datetime.now()
    conversation.last_message_type = message_type

    # 更新未读数
    if conversation.user1_id == receiver_id:
        conversation.user1_unread += 1
        conversation.user1_deleted = 0  # 恢复被删除的会话
    else:
        conversation.user2_unread += 1
        conversation.user2_deleted = 0

    db.commit()
    db.refresh(message)

    return success(data={
        "id": message.id,
        "conversation_id": conversation_id,
        "content": message.content,
        "message_type": message.message_type,
        "created_at": message.created_at.isoformat() if message.created_at else None
    }, message="发送成功")


@router.post("/messages/{message_id}/read", summary="标记消息已读")
async def mark_message_read(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """标记单条消息已读"""
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.receiver_id == current_user.id
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="消息不存在")

    if not message.is_read:
        message.is_read = 1
        message.read_at = datetime.now()
        db.commit()

    return success(message="已读")


@router.delete("/messages/{message_id}", summary="删除消息")
async def delete_message(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除消息（仅发送者可删除）"""
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.sender_id == current_user.id
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="消息不存在或无权删除")

    db.delete(message)
    db.commit()

    return success(message="消息已删除")


# ==================== 未读统计 ====================

@router.get("/unread-summary", summary="获取未读消息汇总")
async def get_unread_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取所有未读消息汇总"""
    # 通知未读数
    notification_count = db.query(func.count(Notification.id)).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == 0
    ).scalar() or 0

    # 私信未读数
    message_count = db.query(func.sum(
        func.if_(
            Conversation.user1_id == current_user.id,
            Conversation.user1_unread,
            Conversation.user2_unread
        )
    )).filter(
        or_(
            Conversation.user1_id == current_user.id,
            Conversation.user2_id == current_user.id
        )
    ).scalar() or 0

    # 分类统计通知
    notification_types = db.query(
        Notification.notify_type,
        func.count(Notification.id)
    ).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == 0
    ).group_by(Notification.notify_type).all()

    type_counts = {t: c for t, c in notification_types}

    return success(data={
        "total": notification_count + message_count,
        "notifications": notification_count,
        "messages": int(message_count),
        "notification_types": type_counts
    })


# ==================== 通知服务函数（供其他模块调用） ====================

async def create_notification(
    db: Session,
    user_id: int,
    notify_type: str,
    sender_id: int = None,
    target_type: str = None,
    target_id: int = None,
    title: str = None,
    content: str = None,
    extra_data: dict = None
):
    """创建通知（供其他模块调用）"""
    # 检查用户通知设置
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if settings:
        # 根据通知类型检查是否启用
        if notify_type == "like" and not settings.notify_like:
            return None
        if notify_type == "comment" and not settings.notify_comment:
            return None
        if notify_type == "follow" and not settings.notify_follow:
            return None

    notification = Notification(
        user_id=user_id,
        sender_id=sender_id,
        notify_type=notify_type,
        target_type=target_type,
        target_id=target_id,
        title=title,
        content=content,
        extra_data=json.dumps(extra_data) if extra_data else None
    )
    db.add(notification)
    return notification
