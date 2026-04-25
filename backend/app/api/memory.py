"""
PetPal - 长期记忆 API

主要面向"记忆花园" UI：
- GET  /memory/list                  分页查看记忆
- POST /memory                        手动添加一条记忆
- PATCH /memory/{id}                  更新（置顶 / 归档 / 修正）
- DELETE /memory/{id}                 永久删除
- GET  /memory/garden/{avatar_id}     花园整体统计
- GET  /memory/digest/{avatar_id}     周期摘要列表
- POST /memory/decay                  手动触发一次衰减（管理员/调试）
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.models.avatar import PetAvatar
from app.models.memory import PetMemory, MemoryDigest
from app.schemas.memory import (
    CreateMemoryRequest, UpdateMemoryRequest,
    MemoryResponse, MemoryGardenStats, MemoryDigestResponse,
)
from app.utils.deps import get_current_user
from app.utils.response import success, page_response
from app.services import memory_service

router = APIRouter()


def _ensure_avatar_owned(db: Session, avatar_id: int, user_id: int) -> PetAvatar:
    avatar = db.query(PetAvatar).filter(
        PetAvatar.id == avatar_id, PetAvatar.user_id == user_id
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="分身不存在或无权访问")
    return avatar


@router.get("/list")
def list_memories(
    avatar_id: int = Query(..., description="分身ID"),
    memory_type: Optional[str] = Query(None, description="类型过滤"),
    emotion: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页列出记忆。"""
    _ensure_avatar_owned(db, avatar_id, current_user.id)

    q = db.query(PetMemory).filter(
        PetMemory.pet_avatar_id == avatar_id,
        PetMemory.user_id == current_user.id,
    )
    if memory_type:
        q = q.filter(PetMemory.memory_type == memory_type)
    if emotion:
        q = q.filter(PetMemory.emotion == emotion)
    if not include_archived:
        q = q.filter(PetMemory.is_archived.is_(False))

    total = q.count()
    items = (
        q.order_by(desc(PetMemory.is_pinned), desc(PetMemory.importance), desc(PetMemory.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return page_response(
        data=[m.to_dict() for m in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("")
def create_memory(
    body: CreateMemoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """主人手动添加一条记忆。"""
    _ensure_avatar_owned(db, body.pet_avatar_id, current_user.id)
    mem = memory_service.write_memory(
        db,
        pet_avatar_id=body.pet_avatar_id,
        user_id=current_user.id,
        content=body.content,
        memory_type=body.memory_type,
        summary=body.summary,
        importance=body.importance,
        emotion=body.emotion,
        emotion_intensity=body.emotion_intensity,
        source="user_input",
        happened_at=body.happened_at,
    )
    db.commit()
    return success(data=mem.to_dict(), message="已添加到记忆")


@router.patch("/{memory_id}")
def update_memory(
    memory_id: int,
    body: UpdateMemoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mem = db.query(PetMemory).filter(
        PetMemory.id == memory_id,
        PetMemory.user_id == current_user.id,
    ).first()
    if not mem:
        raise HTTPException(status_code=404, detail="记忆不存在")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(mem, k, v)
    db.commit()
    return success(data=mem.to_dict())


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """永久删除一条记忆（GDPR 风格的彻底擦除）。"""
    mem = db.query(PetMemory).filter(
        PetMemory.id == memory_id,
        PetMemory.user_id == current_user.id,
    ).first()
    if not mem:
        raise HTTPException(status_code=404, detail="记忆不存在")
    db.delete(mem)
    db.commit()
    return success(message="已删除")


@router.get("/garden/{avatar_id}")
def garden_stats(
    avatar_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """记忆花园 UI 用整体统计。"""
    _ensure_avatar_owned(db, avatar_id, current_user.id)
    stats = memory_service.garden_stats(
        db, pet_avatar_id=avatar_id, user_id=current_user.id
    )
    return success(data=stats)


@router.get("/digest/{avatar_id}")
def list_digests(
    avatar_id: int,
    period_type: str = Query("weekly"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查看周期记忆摘要。"""
    _ensure_avatar_owned(db, avatar_id, current_user.id)
    q = db.query(MemoryDigest).filter(
        MemoryDigest.pet_avatar_id == avatar_id,
        MemoryDigest.user_id == current_user.id,
        MemoryDigest.period_type == period_type,
    )
    total = q.count()
    items = q.order_by(desc(MemoryDigest.period_start)).offset((page - 1) * page_size).limit(page_size).all()
    return page_response(
        data=[m.to_dict() for m in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/{memory_id}/pin")
def toggle_pin(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mem = db.query(PetMemory).filter(
        PetMemory.id == memory_id,
        PetMemory.user_id == current_user.id,
    ).first()
    if not mem:
        raise HTTPException(status_code=404, detail="记忆不存在")
    mem.is_pinned = not bool(mem.is_pinned)
    if mem.is_pinned:
        mem.is_archived = False
    db.commit()
    return success(data={"id": mem.id, "is_pinned": mem.is_pinned})
