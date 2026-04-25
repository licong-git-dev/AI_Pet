"""
PetPal - 设备绑定 API

完整绑定生命周期：
1. POST /devices/pair/start       设备侧调用，拿到 pairing_code（pending 状态）
2. POST /devices/pair/confirm     主人 App 输入 code，绑定归属并切到 online
3. POST /devices/heartbeat        设备定期心跳保活
4. GET  /devices/me               主人查看自己已绑定的设备列表
5. POST /devices/{id}/revoke      解绑（status=revoked）
6. POST /devices/{id}/bind-avatar 切换该设备绑定的分身
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.models.device import DeviceBinding
from app.models.avatar import PetAvatar
from app.schemas.device import (
    StartPairingRequest, StartPairingResponse,
    ConfirmPairingRequest, HeartbeatRequest,
)
from app.utils.deps import get_current_user
from app.utils.response import success

router = APIRouter()


PAIRING_TTL_MINUTES = 10


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ========== 设备侧（无需鉴权，靠 device_id + 配对码闭环）==========

@router.post("/pair/start")
def start_pairing(body: StartPairingRequest, db: Session = Depends(get_db)):
    """
    设备开机/首次启动 → 调用本接口拿到配对码，
    把配对码显示在屏幕上让主人输入到 App。
    """
    existing = db.query(DeviceBinding).filter(
        DeviceBinding.device_type == body.device_type,
        DeviceBinding.device_id == body.device_id,
    ).first()

    code = DeviceBinding.generate_pairing_code()
    expires = _now() + timedelta(minutes=PAIRING_TTL_MINUTES)

    if existing:
        # 已存在：重置为 pending 并更新配对码
        existing.status = "pending"
        existing.pairing_code = code
        existing.pairing_expires_at = expires
        existing.user_id = existing.user_id  # 保留旧归属，确认时再切
        binding = existing
    else:
        binding = DeviceBinding(
            user_id=0,  # 占位，confirm 时回填
            device_type=body.device_type,
            device_id=body.device_id,
            device_name=body.device_name,
            capabilities=body.capabilities,
            transport=body.transport,
            pairing_code=code,
            pairing_expires_at=expires,
            status="pending",
        )
        db.add(binding)
    db.flush()
    db.commit()

    return success(data=StartPairingResponse(
        pairing_code=code,
        expires_at=expires,
        binding_id=binding.id,
    ).model_dump(mode="json"))


@router.post("/heartbeat")
def heartbeat(body: HeartbeatRequest, db: Session = Depends(get_db)):
    """设备心跳。已绑定的设备每 30s 调一次保持 online。"""
    b = db.query(DeviceBinding).filter(DeviceBinding.id == body.binding_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="binding 不存在")
    if b.status == "revoked":
        raise HTTPException(status_code=403, detail="设备已解绑")
    b.last_seen_at = _now()
    if body.capabilities:
        b.capabilities = body.capabilities
    if b.status == "offline":
        b.status = "online"
    db.commit()
    return success(data={"status": b.status})


# ========== 主人侧 ==========

@router.post("/pair/confirm")
def confirm_pairing(
    body: ConfirmPairingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    b = db.query(DeviceBinding).filter(
        DeviceBinding.pairing_code == body.pairing_code.upper(),
        DeviceBinding.status == "pending",
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="配对码无效或已使用")
    if b.pairing_expires_at and b.pairing_expires_at < _now():
        raise HTTPException(status_code=410, detail="配对码已过期")

    if body.pet_avatar_id:
        avatar = db.query(PetAvatar).filter(
            PetAvatar.id == body.pet_avatar_id,
            PetAvatar.user_id == current_user.id,
        ).first()
        if not avatar:
            raise HTTPException(status_code=404, detail="分身不存在或无权访问")

    b.user_id = current_user.id
    b.pet_avatar_id = body.pet_avatar_id
    b.device_name = body.device_name or b.device_name
    b.status = "online"
    b.pairing_code = None
    b.pairing_expires_at = None
    b.last_seen_at = _now()
    db.commit()

    logger.info(f"[devices] confirm user={current_user.id} device={b.device_type}/{b.device_id}")
    return success(data=b.to_dict(), message="设备已绑定")


@router.get("/me")
def list_my_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(DeviceBinding).filter(
        DeviceBinding.user_id == current_user.id,
        DeviceBinding.status != "revoked",
    ).order_by(desc(DeviceBinding.created_at)).all()
    return success(data=[b.to_dict() for b in items])


@router.post("/{binding_id}/revoke")
def revoke_device(
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    b = db.query(DeviceBinding).filter(
        DeviceBinding.id == binding_id,
        DeviceBinding.user_id == current_user.id,
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="设备不存在")
    b.status = "revoked"
    db.commit()
    return success(message="设备已解绑")


@router.post("/{binding_id}/bind-avatar")
def bind_avatar(
    binding_id: int,
    pet_avatar_id: int = Query(..., description="目标分身ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    b = db.query(DeviceBinding).filter(
        DeviceBinding.id == binding_id,
        DeviceBinding.user_id == current_user.id,
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="设备不存在")
    avatar = db.query(PetAvatar).filter(
        PetAvatar.id == pet_avatar_id,
        PetAvatar.user_id == current_user.id,
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="分身不存在或无权访问")
    b.pet_avatar_id = pet_avatar_id
    db.commit()
    return success(data=b.to_dict())
