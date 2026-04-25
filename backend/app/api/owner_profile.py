"""
PetPal - 主人画像 API

- GET    /owner-profile/me                自己的画像
- PATCH  /owner-profile/me                手动修正
- POST   /owner-profile/rebuild           手动触发重建
- POST   /owner-profile/pause             暂停学习 N 天
- POST   /owner-profile/resume            恢复学习
- POST   /owner-profile/signal            前端主动上报一条信号
- GET    /owner-profile/signals           查看自己的原始信号
- DELETE /owner-profile/me                清空我的画像（GDPR）
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.owner_profile import OwnerProfile, OwnerSignal
from app.schemas.owner_profile import (
    OwnerProfileResponse, UpdateProfileRequest, PauseLearningRequest,
    RecordSignalRequest,
)
from app.utils.deps import get_current_user
from app.utils.response import success, page_response
from app.services import owner_profile_service

router = APIRouter()


@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = db.query(OwnerProfile).filter(OwnerProfile.user_id == current_user.id).first()
    if not p:
        # 首次访问：返回空壳
        return success(data={
            "user_id": current_user.id,
            "confidence_score": 0.0,
            "signal_count": 0,
            "last_built_at": None,
            "is_visible_to_avatar": True,
            "is_learning_paused": False,
        })
    return success(data=p.to_dict())


@router.patch("/me")
def update_my_profile(
    body: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    overrides = body.model_dump(exclude_unset=True)
    p = owner_profile_service.apply_user_overrides(
        db, user_id=current_user.id, overrides=overrides
    )
    db.commit()
    return success(data=p.to_dict(), message="画像已更新")


@router.post("/rebuild")
def rebuild_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动触发画像重建（也可通过 Celery 周期执行）。"""
    p = owner_profile_service.build_profile(db, user_id=current_user.id, window_days=30)
    db.commit()
    return success(data=p.to_dict(), message="画像已重建")


@router.post("/pause")
def pause(
    body: PauseLearningRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = owner_profile_service.pause_learning(db, user_id=current_user.id, days=body.days)
    db.commit()
    return success(data={"is_learning_paused": p.is_learning_paused, "pause_until": p.pause_until.isoformat() if p.pause_until else None})


@router.post("/resume")
def resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = owner_profile_service.resume_learning(db, user_id=current_user.id)
    db.commit()
    return success(data={"is_learning_paused": p.is_learning_paused})


@router.post("/signal")
def record_signal(
    body: RecordSignalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sig = owner_profile_service.record_signal(
        db,
        user_id=current_user.id,
        signal_type=body.signal_type,
        payload=body.payload,
        text_excerpt=body.text_excerpt,
    )
    db.commit()
    if sig is None:
        return success(message="学习已暂停，未记录")
    return success(data={"id": sig.id})


@router.get("/signals")
def list_my_signals(
    signal_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(OwnerSignal).filter(OwnerSignal.user_id == current_user.id)
    if signal_type:
        q = q.filter(OwnerSignal.signal_type == signal_type)
    total = q.count()
    items = q.order_by(desc(OwnerSignal.recorded_at)).offset((page - 1) * page_size).limit(page_size).all()
    return page_response(
        data=[s.to_dict() for s in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.delete("/me")
def wipe_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """完全擦除画像 + 信号（隐私要求，不可逆）。"""
    db.query(OwnerSignal).filter(OwnerSignal.user_id == current_user.id).delete()
    db.query(OwnerProfile).filter(OwnerProfile.user_id == current_user.id).delete()
    db.commit()
    return success(message="画像与信号已彻底清除")
