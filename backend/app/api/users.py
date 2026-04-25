"""
PetPal - 用户API

提供用户个人中心完整功能：
- 个人信息管理
- 用户统计数据
- 用户设置（隐私、通知、推送）
- 收货地址管理
- 关注/粉丝管理
- 黑名单管理
- 用户搜索
- 反馈与举报
"""
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.content import Post, Comment, Like
from app.models.health import HealthRecord, HealthConsultation
from app.models.social import Follow
from app.models.user_settings import UserSettings, UserBlacklist, UserAddress, UserFeedback, UserReport
from app.schemas.user import (
    UpdateProfileRequest, UpdatePrivacyRequest, UpdateNotificationRequest,
    UpdatePushRequest, UpdateDisplayRequest, AddressCreate, AddressUpdate,
    FeedbackCreate, ReportCreate, BlockUserRequest
)
from app.utils.deps import get_current_user
from app.utils.response import success, page_response

router = APIRouter()


# ==================== 个人信息 ====================

@router.get("/profile", summary="获取当前用户信息")
async def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前登录用户的个人信息"""
    return success(data=current_user.to_dict())


@router.put("/profile", summary="更新用户信息")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新当前用户的个人信息"""
    update_data = request.model_dump(exclude_unset=True)

    # 检查邮箱是否已被使用
    if "email" in update_data and update_data["email"]:
        existing = db.query(User).filter(
            User.email == update_data["email"],
            User.id != current_user.id,
            User.deleted_at.is_(None)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="该邮箱已被使用")

    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    return success(data=current_user.to_dict(), message="更新成功")


@router.get("/profile/statistics", summary="获取用户统计数据")
async def get_user_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的详细统计数据"""
    # 计算各项统计
    pets_count = db.query(Pet).filter(
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).count()

    posts_count = db.query(Post).filter(
        Post.author_id == current_user.id,
        Post.deleted_at.is_(None)
    ).count()

    comments_count = db.query(Comment).filter(
        Comment.user_id == current_user.id,
        Comment.deleted_at.is_(None)
    ).count()

    health_records_count = db.query(HealthRecord).filter(
        HealthRecord.user_id == current_user.id
    ).count()

    consultations_count = db.query(HealthConsultation).filter(
        HealthConsultation.user_id == current_user.id
    ).count()

    # 计算注册天数
    days_joined = 0
    if current_user.created_at:
        days_joined = (datetime.now() - current_user.created_at).days

    statistics = {
        "pets_count": pets_count,
        "posts_count": posts_count,
        "comments_count": comments_count,
        "likes_count": current_user.likes_count,
        "followers_count": current_user.followers_count,
        "following_count": current_user.following_count,
        "health_records_count": health_records_count,
        "consultations_count": consultations_count,
        "points": current_user.points,
        "member_level": current_user.member_level,
        "member_expire_at": current_user.member_expire_at.isoformat() if current_user.member_expire_at else None,
        "days_joined": days_joined
    }

    return success(data=statistics)


@router.get("/{user_id}", summary="获取用户信息")
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定用户的公开信息"""
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否被当前用户拉黑或拉黑了当前用户
    is_blocked_by_me = db.query(UserBlacklist).filter(
        UserBlacklist.user_id == current_user.id,
        UserBlacklist.blocked_user_id == user_id
    ).first() is not None

    is_blocked_me = db.query(UserBlacklist).filter(
        UserBlacklist.user_id == user_id,
        UserBlacklist.blocked_user_id == current_user.id
    ).first() is not None

    if is_blocked_me:
        raise HTTPException(status_code=403, detail="无法查看该用户信息")

    # 获取用户设置检查隐私
    user_settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

    user_data = user.to_dict()

    # 检查是否已关注
    is_following = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first() is not None

    user_data["is_following"] = is_following
    user_data["is_blocked"] = is_blocked_by_me

    # 隐私检查
    if user_settings:
        if user_settings.profile_visibility == "private" and user_id != current_user.id:
            if not is_following:
                # 私密账户，只返回基本信息
                return success(data={
                    "id": user.id,
                    "nickname": user.nickname,
                    "avatar_url": user.avatar_url,
                    "is_private": True,
                    "is_following": is_following,
                    "is_blocked": is_blocked_by_me
                })

        if user_settings.profile_visibility == "followers" and user_id != current_user.id:
            # 检查是否是粉丝
            is_follower = db.query(Follow).filter(
                Follow.follower_id == user_id,
                Follow.following_id == current_user.id
            ).first() is not None

            if not is_following and not is_follower:
                return success(data={
                    "id": user.id,
                    "nickname": user.nickname,
                    "avatar_url": user.avatar_url,
                    "is_followers_only": True,
                    "is_following": is_following,
                    "is_blocked": is_blocked_by_me
                })

    return success(data=user_data)


@router.get("/{user_id}/detail", summary="获取用户详情")
async def get_user_detail(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户详细信息（含统计和最近动态）"""
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查拉黑状态
    is_blocked_me = db.query(UserBlacklist).filter(
        UserBlacklist.user_id == user_id,
        UserBlacklist.blocked_user_id == current_user.id
    ).first() is not None

    if is_blocked_me:
        raise HTTPException(status_code=403, detail="无法查看该用户信息")

    user_data = user.to_dict()

    # 关注状态
    is_following = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first() is not None
    user_data["is_following"] = is_following

    # 统计数据
    pets_count = db.query(Pet).filter(Pet.owner_id == user_id, Pet.deleted_at.is_(None)).count()
    posts_count = db.query(Post).filter(Post.author_id == user_id, Post.deleted_at.is_(None)).count()

    user_data["statistics"] = {
        "pets_count": pets_count,
        "posts_count": posts_count,
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "likes_count": user.likes_count
    }

    # 最近宠物（3个）
    recent_pets = db.query(Pet).filter(
        Pet.owner_id == user_id,
        Pet.deleted_at.is_(None)
    ).order_by(Pet.created_at.desc()).limit(3).all()
    user_data["recent_pets"] = [pet.to_dict() for pet in recent_pets]

    # 最近帖子（5个）
    recent_posts = db.query(Post).filter(
        Post.author_id == user_id,
        Post.deleted_at.is_(None),
        Post.status == "published"
    ).order_by(Post.created_at.desc()).limit(5).all()
    user_data["recent_posts"] = [post.to_dict() for post in recent_posts]

    return success(data=user_data)


# ==================== 用户设置 ====================

def get_or_create_settings(db: Session, user_id: int) -> UserSettings:
    """获取或创建用户设置"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/settings/all", summary="获取所有设置")
async def get_all_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户所有设置"""
    settings = get_or_create_settings(db, current_user.id)
    return success(data=settings.to_dict())


@router.get("/settings/privacy", summary="获取隐私设置")
async def get_privacy_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取隐私设置"""
    settings = get_or_create_settings(db, current_user.id)
    return success(data={
        "profile_visibility": settings.profile_visibility,
        "show_online_status": bool(settings.show_online_status),
        "show_pet_list": bool(settings.show_pet_list),
        "allow_stranger_message": bool(settings.allow_stranger_message),
        "allow_comment": bool(settings.allow_comment),
        "show_location": bool(settings.show_location)
    })


@router.put("/settings/privacy", summary="更新隐私设置")
async def update_privacy_settings(
    request: UpdatePrivacyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新隐私设置"""
    settings = get_or_create_settings(db, current_user.id)
    update_data = request.model_dump(exclude_unset=True)

    # 转换布尔值为整数
    field_mapping = {
        "profile_visibility": "profile_visibility",
        "show_online_status": "show_online_status",
        "show_pet_list": "show_pet_list",
        "allow_stranger_message": "allow_stranger_message",
        "allow_comment": "allow_comment",
        "show_location": "show_location"
    }

    for key, value in update_data.items():
        if key in field_mapping:
            if isinstance(value, bool):
                value = 1 if value else 0
            setattr(settings, field_mapping[key], value)

    db.commit()

    return success(message="隐私设置已更新")


@router.get("/settings/notifications", summary="获取通知设置")
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取通知设置"""
    settings = get_or_create_settings(db, current_user.id)
    return success(data={
        "like": bool(settings.notify_like),
        "comment": bool(settings.notify_comment),
        "follow": bool(settings.notify_follow),
        "message": bool(settings.notify_message),
        "system": bool(settings.notify_system),
        "activity": bool(settings.notify_activity),
        "health_reminder": bool(settings.notify_health_reminder)
    })


@router.put("/settings/notifications", summary="更新通知设置")
async def update_notification_settings(
    request: UpdateNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新通知设置"""
    settings = get_or_create_settings(db, current_user.id)
    update_data = request.model_dump(exclude_unset=True)

    field_mapping = {
        "like": "notify_like",
        "comment": "notify_comment",
        "follow": "notify_follow",
        "message": "notify_message",
        "system": "notify_system",
        "activity": "notify_activity",
        "health_reminder": "notify_health_reminder"
    }

    for key, value in update_data.items():
        if key in field_mapping:
            setattr(settings, field_mapping[key], 1 if value else 0)

    db.commit()

    return success(message="通知设置已更新")


@router.put("/settings/push", summary="更新推送设置")
async def update_push_settings(
    request: UpdatePushRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新推送设置"""
    settings = get_or_create_settings(db, current_user.id)
    update_data = request.model_dump(exclude_unset=True)

    if "enabled" in update_data:
        settings.push_enabled = 1 if update_data["enabled"] else 0
    if "quiet_start" in update_data:
        settings.push_quiet_start = update_data["quiet_start"]
    if "quiet_end" in update_data:
        settings.push_quiet_end = update_data["quiet_end"]

    db.commit()

    return success(message="推送设置已更新")


@router.put("/settings/display", summary="更新显示设置")
async def update_display_settings(
    request: UpdateDisplayRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新显示设置"""
    settings = get_or_create_settings(db, current_user.id)
    update_data = request.model_dump(exclude_unset=True)

    for key in ["language", "theme", "font_size"]:
        if key in update_data:
            setattr(settings, key, update_data[key])

    db.commit()

    return success(message="显示设置已更新")


# ==================== 关注/粉丝 ====================

@router.post("/{user_id}/follow", summary="关注用户")
async def follow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """关注指定用户"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能关注自己")

    target_user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否被对方拉黑
    is_blocked = db.query(UserBlacklist).filter(
        UserBlacklist.user_id == user_id,
        UserBlacklist.blocked_user_id == current_user.id
    ).first()
    if is_blocked:
        raise HTTPException(status_code=403, detail="无法关注该用户")

    # 检查是否已关注
    existing = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已关注该用户")

    # 创建关注关系
    follow = Follow(follower_id=current_user.id, following_id=user_id)
    db.add(follow)

    # 更新计数
    current_user.following_count += 1
    target_user.followers_count += 1

    db.commit()

    return success(message="关注成功")


@router.delete("/{user_id}/follow", summary="取消关注")
async def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消关注指定用户"""
    follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()

    if not follow:
        raise HTTPException(status_code=400, detail="未关注该用户")

    db.delete(follow)

    # 更新计数
    current_user.following_count = max(0, current_user.following_count - 1)
    target_user = db.query(User).filter(User.id == user_id).first()
    if target_user:
        target_user.followers_count = max(0, target_user.followers_count - 1)

    db.commit()

    return success(message="取消关注成功")


@router.get("/{user_id}/followers", summary="获取粉丝列表")
async def get_followers(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的粉丝列表"""
    query = db.query(User).join(Follow, Follow.follower_id == User.id).filter(
        Follow.following_id == user_id,
        User.deleted_at.is_(None)
    )

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取当前用户关注的人列表
    following_ids = set()
    if current_user:
        following = db.query(Follow.following_id).filter(
            Follow.follower_id == current_user.id
        ).all()
        following_ids = {f[0] for f in following}

    result = []
    for user in users:
        user_data = user.to_dict()
        user_data["is_following"] = user.id in following_ids
        result.append(user_data)

    return page_response(
        data=result,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/{user_id}/following", summary="获取关注列表")
async def get_following(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的关注列表"""
    query = db.query(User).join(Follow, Follow.following_id == User.id).filter(
        Follow.follower_id == user_id,
        User.deleted_at.is_(None)
    )

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取当前用户关注的人列表
    following_ids = set()
    if current_user:
        following = db.query(Follow.following_id).filter(
            Follow.follower_id == current_user.id
        ).all()
        following_ids = {f[0] for f in following}

    result = []
    for user in users:
        user_data = user.to_dict()
        user_data["is_following"] = user.id in following_ids
        result.append(user_data)

    return page_response(
        data=result,
        page=page,
        page_size=page_size,
        total=total
    )


# ==================== 黑名单管理 ====================

@router.get("/blacklist/list", summary="获取黑名单")
async def get_blacklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的黑名单列表"""
    query = db.query(UserBlacklist, User).join(
        User, UserBlacklist.blocked_user_id == User.id
    ).filter(
        UserBlacklist.user_id == current_user.id
    )

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for blacklist, user in records:
        result.append({
            "id": blacklist.id,
            "user_id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "reason": blacklist.reason,
            "blocked_at": blacklist.created_at.isoformat() if blacklist.created_at else None
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.post("/blacklist", summary="拉黑用户")
async def block_user(
    request: BlockUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """拉黑指定用户"""
    if request.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能拉黑自己")

    # 检查用户是否存在
    target_user = db.query(User).filter(
        User.id == request.user_id,
        User.deleted_at.is_(None)
    ).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否已拉黑
    existing = db.query(UserBlacklist).filter(
        UserBlacklist.user_id == current_user.id,
        UserBlacklist.blocked_user_id == request.user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已在黑名单中")

    # 添加到黑名单
    blacklist = UserBlacklist(
        user_id=current_user.id,
        blocked_user_id=request.user_id,
        reason=request.reason
    )
    db.add(blacklist)

    # 取消双方关注关系
    db.query(Follow).filter(
        or_(
            (Follow.follower_id == current_user.id) & (Follow.following_id == request.user_id),
            (Follow.follower_id == request.user_id) & (Follow.following_id == current_user.id)
        )
    ).delete(synchronize_session=False)

    # 更新关注计数
    current_user.following_count = db.query(Follow).filter(
        Follow.follower_id == current_user.id
    ).count()
    current_user.followers_count = db.query(Follow).filter(
        Follow.following_id == current_user.id
    ).count()

    target_user.following_count = db.query(Follow).filter(
        Follow.follower_id == target_user.id
    ).count()
    target_user.followers_count = db.query(Follow).filter(
        Follow.following_id == target_user.id
    ).count()

    db.commit()

    return success(message="已将用户加入黑名单")


@router.delete("/blacklist/{user_id}", summary="移出黑名单")
async def unblock_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """将用户移出黑名单"""
    blacklist = db.query(UserBlacklist).filter(
        UserBlacklist.user_id == current_user.id,
        UserBlacklist.blocked_user_id == user_id
    ).first()

    if not blacklist:
        raise HTTPException(status_code=404, detail="该用户不在黑名单中")

    db.delete(blacklist)
    db.commit()

    return success(message="已将用户移出黑名单")


# ==================== 收货地址 ====================

@router.get("/addresses", summary="获取收货地址列表")
async def get_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的收货地址列表"""
    addresses = db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id
    ).order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc()).all()

    return success(data=[addr.to_dict() for addr in addresses])


@router.post("/addresses", summary="添加收货地址")
async def create_address(
    request: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加新的收货地址"""
    # 检查地址数量限制
    count = db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id
    ).count()
    if count >= 20:
        raise HTTPException(status_code=400, detail="最多保存20个收货地址")

    # 如果设为默认，取消其他默认地址
    if request.is_default:
        db.query(UserAddress).filter(
            UserAddress.user_id == current_user.id,
            UserAddress.is_default == 1
        ).update({"is_default": 0})

    address = UserAddress(
        user_id=current_user.id,
        receiver_name=request.receiver_name,
        receiver_phone=request.receiver_phone,
        province=request.province,
        city=request.city,
        district=request.district,
        detail_address=request.detail_address,
        postal_code=request.postal_code,
        tag=request.tag,
        is_default=1 if request.is_default else 0
    )
    db.add(address)
    db.commit()
    db.refresh(address)

    return success(data=address.to_dict(), message="地址添加成功")


@router.put("/addresses/{address_id}", summary="更新收货地址")
async def update_address(
    address_id: int,
    request: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新收货地址"""
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(status_code=404, detail="地址不存在")

    update_data = request.model_dump(exclude_unset=True)

    # 如果设为默认，取消其他默认地址
    if update_data.get("is_default"):
        db.query(UserAddress).filter(
            UserAddress.user_id == current_user.id,
            UserAddress.id != address_id,
            UserAddress.is_default == 1
        ).update({"is_default": 0})
        update_data["is_default"] = 1
    elif "is_default" in update_data:
        update_data["is_default"] = 1 if update_data["is_default"] else 0

    for key, value in update_data.items():
        setattr(address, key, value)

    db.commit()
    db.refresh(address)

    return success(data=address.to_dict(), message="地址更新成功")


@router.delete("/addresses/{address_id}", summary="删除收货地址")
async def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除收货地址"""
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(status_code=404, detail="地址不存在")

    db.delete(address)
    db.commit()

    return success(message="地址删除成功")


@router.put("/addresses/{address_id}/default", summary="设为默认地址")
async def set_default_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """设置默认收货地址"""
    address = db.query(UserAddress).filter(
        UserAddress.id == address_id,
        UserAddress.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(status_code=404, detail="地址不存在")

    # 取消其他默认地址
    db.query(UserAddress).filter(
        UserAddress.user_id == current_user.id,
        UserAddress.is_default == 1
    ).update({"is_default": 0})

    address.is_default = 1
    db.commit()

    return success(message="已设为默认地址")


# ==================== 用户搜索 ====================

@router.get("/search/users", summary="搜索用户")
async def search_users(
    keyword: str = Query(..., min_length=1, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """搜索用户"""
    # 搜索昵称或手机号后四位
    query = db.query(User).filter(
        User.deleted_at.is_(None),
        User.status == 1,
        or_(
            User.nickname.ilike(f"%{keyword}%"),
            User.phone.like(f"%{keyword}")
        )
    )

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取当前用户关注的人列表
    following_ids = set()
    following = db.query(Follow.following_id).filter(
        Follow.follower_id == current_user.id
    ).all()
    following_ids = {f[0] for f in following}

    result = []
    for user in users:
        result.append({
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "bio": user.bio[:50] if user.bio else None,
            "followers_count": user.followers_count,
            "is_following": user.id in following_ids
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


# ==================== 反馈与举报 ====================

@router.post("/feedback", summary="提交反馈")
async def create_feedback(
    request: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交用户反馈"""
    feedback = UserFeedback(
        user_id=current_user.id,
        feedback_type=request.feedback_type,
        content=request.content,
        images=json.dumps(request.images) if request.images else None,
        contact=request.contact
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return success(data=feedback.to_dict(), message="反馈提交成功，我们会尽快处理")


@router.get("/feedback/list", summary="获取我的反馈")
async def get_my_feedbacks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我提交的反馈列表"""
    query = db.query(UserFeedback).filter(
        UserFeedback.user_id == current_user.id
    ).order_by(UserFeedback.created_at.desc())

    total = query.count()
    feedbacks = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[f.to_dict() for f in feedbacks],
        page=page,
        page_size=page_size,
        total=total
    )


@router.post("/report", summary="提交举报")
async def create_report(
    request: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交举报"""
    # 检查是否已举报过
    existing = db.query(UserReport).filter(
        UserReport.reporter_id == current_user.id,
        UserReport.target_type == request.target_type,
        UserReport.target_id == request.target_id,
        UserReport.status.in_(["pending", "processing"])
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="您已提交过该举报，请等待处理")

    report = UserReport(
        reporter_id=current_user.id,
        target_type=request.target_type,
        target_id=request.target_id,
        reason=request.reason,
        description=request.description,
        evidence_images=json.dumps(request.evidence_images) if request.evidence_images else None
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return success(data=report.to_dict(), message="举报提交成功，我们会尽快处理")


@router.get("/report/list", summary="获取我的举报")
async def get_my_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我提交的举报列表"""
    query = db.query(UserReport).filter(
        UserReport.reporter_id == current_user.id
    ).order_by(UserReport.created_at.desc())

    total = query.count()
    reports = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[r.to_dict() for r in reports],
        page=page,
        page_size=page_size,
        total=total
    )
