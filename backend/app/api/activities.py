"""
PetPal - 线下活动API

提供完整的活动功能：
- 活动发布与管理
- 活动报名与签到
- 活动搜索与推荐
- 参与者管理
"""
import json
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_, func
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.social import Activity, ActivityParticipant, Notification
from app.utils.deps import get_current_user, get_current_user_optional
from app.utils.response import success, page_response

router = APIRouter()


# ==================== Schema定义 ====================

class CreateActivityRequest(BaseModel):
    """创建活动请求"""
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    cover_image: Optional[str] = None
    images: Optional[List[str]] = Field(None, max_length=9)
    activity_type: str = Field(..., pattern="^(walk|party|competition|charity|training|other)$")
    start_time: datetime
    end_time: Optional[datetime] = None
    location_name: Optional[str] = Field(None, max_length=200)
    location_address: Optional[str] = Field(None, max_length=500)
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    max_participants: int = Field(0, ge=0, description="0表示不限人数")
    fee: float = Field(0, ge=0)
    pet_types: Optional[List[str]] = None
    pet_required: bool = False


class UpdateActivityRequest(BaseModel):
    """更新活动请求"""
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    cover_image: Optional[str] = None
    images: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location_name: Optional[str] = None
    location_address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    max_participants: Optional[int] = None
    fee: Optional[float] = None
    pet_types: Optional[List[str]] = None
    pet_required: Optional[bool] = None


class JoinActivityRequest(BaseModel):
    """报名活动请求"""
    pet_id: Optional[int] = None
    remark: Optional[str] = Field(None, max_length=200)


# ==================== 辅助函数 ====================

def _format_activity(activity: Activity, current_user: User = None, db: Session = None) -> dict:
    """格式化活动数据"""
    activity_dict = activity.to_dict()

    # 解析JSON字段
    try:
        activity_dict["images"] = json.loads(activity.images) if activity.images else []
    except (json.JSONDecodeError, ValueError):
        activity_dict["images"] = []

    try:
        activity_dict["pet_types"] = json.loads(activity.pet_types) if activity.pet_types else []
    except (json.JSONDecodeError, ValueError):
        activity_dict["pet_types"] = []

    activity_dict["pet_required"] = bool(activity.pet_required)

    # 获取创建者信息
    if db:
        creator = db.query(User).filter(User.id == activity.creator_id).first()
        if creator:
            activity_dict["creator"] = {
                "id": creator.id,
                "nickname": creator.nickname,
                "avatar_url": creator.avatar_url
            }

    # 检查当前用户是否已报名
    activity_dict["is_joined"] = False
    activity_dict["is_creator"] = False
    if current_user and db:
        if activity.creator_id == current_user.id:
            activity_dict["is_creator"] = True

        participant = db.query(ActivityParticipant).filter(
            ActivityParticipant.activity_id == activity.id,
            ActivityParticipant.user_id == current_user.id,
            ActivityParticipant.status != "cancelled"
        ).first()
        if participant:
            activity_dict["is_joined"] = True
            activity_dict["join_status"] = participant.status

    return activity_dict


# ==================== 活动列表与搜索 ====================

@router.get("", summary="获取活动列表")
async def get_activities(
    activity_type: Optional[str] = Query(None, description="活动类型"),
    status: Optional[str] = Query(None, description="状态: upcoming/ongoing/completed"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    pet_type: Optional[str] = Query(None, description="宠物类型筛选"),
    latitude: Optional[float] = Query(None, description="纬度（附近活动）"),
    longitude: Optional[float] = Query(None, description="经度（附近活动）"),
    sort: str = Query("time", description="排序: time/hot/near"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取活动列表"""
    query = db.query(Activity).filter(Activity.status != "cancelled")

    # 类型筛选
    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)

    # 状态筛选
    now = datetime.now()
    if status == "upcoming":
        query = query.filter(Activity.start_time > now, Activity.status == "upcoming")
    elif status == "ongoing":
        query = query.filter(
            Activity.start_time <= now,
            or_(Activity.end_time.is_(None), Activity.end_time > now),
            Activity.status == "ongoing"
        )
    elif status == "completed":
        query = query.filter(Activity.status == "completed")

    # 关键词搜索
    if keyword:
        keyword_filter = f"%{keyword}%"
        query = query.filter(
            or_(
                Activity.title.ilike(keyword_filter),
                Activity.description.ilike(keyword_filter),
                Activity.location_name.ilike(keyword_filter)
            )
        )

    # 宠物类型筛选
    if pet_type:
        query = query.filter(
            or_(
                Activity.pet_types.is_(None),
                Activity.pet_types.contains(pet_type)
            )
        )

    # 排序
    if sort == "hot":
        query = query.order_by(desc(Activity.current_participants), desc(Activity.views_count))
    elif sort == "near" and latitude and longitude:
        # 简单的距离排序（实际项目可用PostGIS）
        query = query.order_by(Activity.start_time)
    else:  # time
        query = query.order_by(Activity.start_time)

    total = query.count()
    activities = query.offset((page - 1) * page_size).limit(page_size).all()

    result = [_format_activity(a, current_user, db) for a in activities]

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/my", summary="我的活动")
async def get_my_activities(
    tab: str = Query("created", description="标签: created创建的 joined参加的"),
    status: Optional[str] = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取我的活动列表"""
    if tab == "created":
        query = db.query(Activity).filter(Activity.creator_id == current_user.id)
    else:  # joined
        query = db.query(Activity).join(
            ActivityParticipant,
            ActivityParticipant.activity_id == Activity.id
        ).filter(
            ActivityParticipant.user_id == current_user.id,
            ActivityParticipant.status != "cancelled"
        )

    if status:
        query = query.filter(Activity.status == status)

    query = query.order_by(desc(Activity.created_at))

    total = query.count()
    activities = query.offset((page - 1) * page_size).limit(page_size).all()

    result = [_format_activity(a, current_user, db) for a in activities]

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/recommend", summary="推荐活动")
async def get_recommended_activities(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取推荐活动"""
    now = datetime.now()

    # 获取即将开始的热门活动
    activities = db.query(Activity).filter(
        Activity.status == "upcoming",
        Activity.start_time > now
    ).order_by(
        desc(Activity.current_participants),
        Activity.start_time
    ).limit(limit).all()

    result = [_format_activity(a, current_user, db) for a in activities]

    return success(data=result)


# ==================== 活动CRUD ====================

@router.post("", summary="创建活动")
async def create_activity(
    request: CreateActivityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建活动"""
    # 验证时间
    if request.start_time < datetime.now():
        raise HTTPException(status_code=400, detail="开始时间不能早于当前时间")

    if request.end_time and request.end_time <= request.start_time:
        raise HTTPException(status_code=400, detail="结束时间必须晚于开始时间")

    activity = Activity(
        creator_id=current_user.id,
        title=request.title,
        description=request.description,
        cover_image=request.cover_image,
        images=json.dumps(request.images) if request.images else None,
        activity_type=request.activity_type,
        start_time=request.start_time,
        end_time=request.end_time,
        location_name=request.location_name,
        location_address=request.location_address,
        latitude=request.latitude,
        longitude=request.longitude,
        max_participants=request.max_participants,
        fee=request.fee,
        pet_types=json.dumps(request.pet_types) if request.pet_types else None,
        pet_required=1 if request.pet_required else 0,
        status="upcoming"
    )
    db.add(activity)
    db.commit()
    db.refresh(activity)

    return success(data=_format_activity(activity, current_user, db), message="活动创建成功")


@router.get("/{activity_id}", summary="获取活动详情")
async def get_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取活动详情"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.status != "cancelled"
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在")

    # 增加浏览量
    activity.views_count += 1
    db.commit()

    result = _format_activity(activity, current_user, db)

    # 获取最新参与者
    recent_participants = db.query(ActivityParticipant).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.status != "cancelled"
    ).order_by(desc(ActivityParticipant.created_at)).limit(10).all()

    participant_ids = [p.user_id for p in recent_participants]
    users = db.query(User).filter(User.id.in_(participant_ids)).all() if participant_ids else []
    user_map = {u.id: {"id": u.id, "nickname": u.nickname, "avatar_url": u.avatar_url} for u in users}

    result["recent_participants"] = [user_map.get(p.user_id) for p in recent_participants if p.user_id in user_map]

    return success(data=result)


@router.put("/{activity_id}", summary="更新活动")
async def update_activity(
    activity_id: int,
    request: UpdateActivityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新活动"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.creator_id == current_user.id
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或无权修改")

    if activity.status not in ["upcoming"]:
        raise HTTPException(status_code=400, detail="活动已开始，无法修改")

    update_data = request.model_dump(exclude_unset=True)

    # 处理JSON字段
    if "images" in update_data and update_data["images"] is not None:
        update_data["images"] = json.dumps(update_data["images"])
    if "pet_types" in update_data and update_data["pet_types"] is not None:
        update_data["pet_types"] = json.dumps(update_data["pet_types"])
    if "pet_required" in update_data:
        update_data["pet_required"] = 1 if update_data["pet_required"] else 0

    for key, value in update_data.items():
        setattr(activity, key, value)

    db.commit()
    db.refresh(activity)

    return success(data=_format_activity(activity, current_user, db), message="更新成功")


@router.delete("/{activity_id}", summary="取消活动")
async def cancel_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消活动"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.creator_id == current_user.id
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或无权操作")

    if activity.status == "completed":
        raise HTTPException(status_code=400, detail="活动已结束，无法取消")

    activity.status = "cancelled"

    # 通知所有参与者
    participants = db.query(ActivityParticipant).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.status != "cancelled"
    ).all()

    for p in participants:
        notification = Notification(
            user_id=p.user_id,
            sender_id=current_user.id,
            notify_type="system",
            target_type="activity",
            target_id=activity_id,
            title="活动取消通知",
            content=f"您报名的活动「{activity.title}」已被取消"
        )
        db.add(notification)
        p.status = "cancelled"

    db.commit()

    return success(message="活动已取消")


# ==================== 活动报名 ====================

@router.post("/{activity_id}/join", summary="报名活动")
async def join_activity(
    activity_id: int,
    request: JoinActivityRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """报名参加活动"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.status == "upcoming"
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或已结束")

    if activity.creator_id == current_user.id:
        raise HTTPException(status_code=400, detail="创建者无需报名")

    # 检查是否已报名
    existing = db.query(ActivityParticipant).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.user_id == current_user.id,
        ActivityParticipant.status != "cancelled"
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="已报名此活动")

    # 检查人数限制
    if activity.max_participants > 0 and activity.current_participants >= activity.max_participants:
        raise HTTPException(status_code=400, detail="活动人数已满")

    # 检查宠物要求
    pet_id = request.pet_id if request else None
    if activity.pet_required:
        if not pet_id:
            raise HTTPException(status_code=400, detail="此活动需要带宠物参加")

        pet = db.query(Pet).filter(
            Pet.id == pet_id,
            Pet.owner_id == current_user.id,
            Pet.deleted_at.is_(None)
        ).first()

        if not pet:
            raise HTTPException(status_code=400, detail="宠物不存在")

        # 检查宠物类型限制
        if activity.pet_types:
            allowed_types = json.loads(activity.pet_types)
            if allowed_types and pet.pet_type not in allowed_types:
                raise HTTPException(status_code=400, detail="您的宠物类型不符合活动要求")

    # 创建报名记录
    participant = ActivityParticipant(
        activity_id=activity_id,
        user_id=current_user.id,
        pet_id=pet_id,
        status="registered"
    )
    db.add(participant)

    # 更新参与人数
    activity.current_participants += 1

    # 通知活动创建者
    notification = Notification(
        user_id=activity.creator_id,
        sender_id=current_user.id,
        notify_type="system",
        target_type="activity",
        target_id=activity_id,
        title="新报名通知",
        content=f"用户 {current_user.nickname} 报名了您的活动「{activity.title}」"
    )
    db.add(notification)

    db.commit()

    return success(message="报名成功")


@router.delete("/{activity_id}/join", summary="取消报名")
async def cancel_join(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消报名"""
    participant = db.query(ActivityParticipant).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.user_id == current_user.id,
        ActivityParticipant.status == "registered"
    ).first()

    if not participant:
        raise HTTPException(status_code=400, detail="未报名此活动")

    activity = db.query(Activity).filter(Activity.id == activity_id).first()

    if activity.status != "upcoming":
        raise HTTPException(status_code=400, detail="活动已开始，无法取消")

    participant.status = "cancelled"
    activity.current_participants = max(0, activity.current_participants - 1)

    db.commit()

    return success(message="取消报名成功")


@router.post("/{activity_id}/check-in", summary="活动签到")
async def check_in(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """活动签到"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.status.in_(["upcoming", "ongoing"])
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或已结束")

    participant = db.query(ActivityParticipant).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.user_id == current_user.id,
        ActivityParticipant.status == "registered"
    ).first()

    if not participant:
        raise HTTPException(status_code=400, detail="未报名此活动")

    if participant.status == "checked_in":
        raise HTTPException(status_code=400, detail="已签到")

    participant.status = "checked_in"
    participant.check_in_time = datetime.now()

    # 奖励积分
    from app.models.points import PointsRecord
    points_earned = 10
    points_record = PointsRecord(
        user_id=current_user.id,
        points=points_earned,
        balance=current_user.points + points_earned,
        source_type="activity",
        source_id=activity_id,
        description=f"参加活动「{activity.title}」签到奖励"
    )
    current_user.points += points_earned
    db.add(points_record)

    db.commit()

    return success(message=f"签到成功，获得{points_earned}积分")


# ==================== 参与者管理 ====================

@router.get("/{activity_id}/participants", summary="获取参与者列表")
async def get_participants(
    activity_id: int,
    status: Optional[str] = Query(None, description="状态: registered/checked_in"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """获取活动参与者列表"""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在")

    query = db.query(ActivityParticipant).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.status != "cancelled"
    )

    if status:
        query = query.filter(ActivityParticipant.status == status)

    query = query.order_by(ActivityParticipant.created_at)

    total = query.count()
    participants = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取用户信息
    user_ids = [p.user_id for p in participants]
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u for u in users}

    # 获取宠物信息
    pet_ids = [p.pet_id for p in participants if p.pet_id]
    pets = db.query(Pet).filter(Pet.id.in_(pet_ids)).all() if pet_ids else []
    pet_map = {p.id: p for p in pets}

    result = []
    for p in participants:
        user = user_map.get(p.user_id)
        pet = pet_map.get(p.pet_id) if p.pet_id else None

        result.append({
            "id": p.id,
            "status": p.status,
            "check_in_time": p.check_in_time.isoformat() if p.check_in_time else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "user": {
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url
            } if user else None,
            "pet": {
                "id": pet.id,
                "name": pet.name,
                "pet_type": pet.pet_type,
                "avatar_url": pet.avatar_url
            } if pet else None
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/{activity_id}/statistics", summary="获取活动统计")
async def get_activity_statistics(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取活动统计数据（仅创建者可见）"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.creator_id == current_user.id
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或无权查看")

    # 统计报名人数
    registered_count = db.query(func.count(ActivityParticipant.id)).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.status == "registered"
    ).scalar() or 0

    # 统计签到人数
    checked_in_count = db.query(func.count(ActivityParticipant.id)).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.status == "checked_in"
    ).scalar() or 0

    # 统计取消人数
    cancelled_count = db.query(func.count(ActivityParticipant.id)).filter(
        ActivityParticipant.activity_id == activity_id,
        ActivityParticipant.status == "cancelled"
    ).scalar() or 0

    # 签到率
    total_valid = registered_count + checked_in_count
    check_in_rate = round(checked_in_count / total_valid * 100, 1) if total_valid > 0 else 0

    return success(data={
        "views_count": activity.views_count,
        "registered_count": registered_count,
        "checked_in_count": checked_in_count,
        "cancelled_count": cancelled_count,
        "total_participants": total_valid,
        "check_in_rate": check_in_rate,
        "max_participants": activity.max_participants
    })


# ==================== 活动状态管理 ====================

@router.post("/{activity_id}/start", summary="开始活动")
async def start_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """开始活动（仅创建者）"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.creator_id == current_user.id,
        Activity.status == "upcoming"
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或无法开始")

    activity.status = "ongoing"
    db.commit()

    return success(message="活动已开始")


@router.post("/{activity_id}/end", summary="结束活动")
async def end_activity(
    activity_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """结束活动（仅创建者）"""
    activity = db.query(Activity).filter(
        Activity.id == activity_id,
        Activity.creator_id == current_user.id,
        Activity.status.in_(["upcoming", "ongoing"])
    ).first()

    if not activity:
        raise HTTPException(status_code=404, detail="活动不存在或无法结束")

    activity.status = "completed"
    db.commit()

    return success(message="活动已结束")
