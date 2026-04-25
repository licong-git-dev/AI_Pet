"""
PetPal - 设备绑定 Pydantic Schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


DeviceType = Literal["web", "mobile", "hologram", "desktop_pet", "ar_glasses"]
Transport = Literal["websocket", "mqtt", "ble_relay", "http_long_poll"]


class StartPairingRequest(BaseModel):
    """设备侧请求开始绑定（设备发起）"""
    device_type: DeviceType
    device_id: str = Field(..., min_length=4, max_length=64)
    device_name: Optional[str] = Field(None, max_length=50)
    capabilities: Optional[Dict[str, Any]] = None
    transport: Transport = "websocket"


class StartPairingResponse(BaseModel):
    pairing_code: str
    expires_at: datetime
    binding_id: int


class ConfirmPairingRequest(BaseModel):
    """主人 App 端输入配对码完成绑定"""
    pairing_code: str = Field(..., min_length=4, max_length=16)
    pet_avatar_id: Optional[int] = None
    device_name: Optional[str] = Field(None, max_length=50)


class HeartbeatRequest(BaseModel):
    """设备心跳"""
    binding_id: int
    capabilities: Optional[Dict[str, Any]] = None


class DeviceBindingResponse(BaseModel):
    id: int
    user_id: int
    pet_avatar_id: Optional[int] = None
    device_type: str
    device_id: str
    device_name: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    transport: str
    status: str
    last_seen_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
