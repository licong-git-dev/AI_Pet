"""
PetPal - 设备绑定模型

记录用户绑定到分身的所有终端：网页 / 移动端 / 全息 / 桌宠 / AR 等。
绑定流程见 docs/PRODUCT_DESIGN.md §3.5
"""
import secrets
from sqlalchemy import (
    Column, BigInteger, String, DateTime, ForeignKey, JSON, Boolean,
    func, text, Index, UniqueConstraint,
)
from app.database import Base


DEVICE_TYPES = ("web", "mobile", "hologram", "desktop_pet", "ar_glasses")
DEVICE_STATUSES = ("pending", "online", "offline", "revoked")
TRANSPORTS = ("websocket", "mqtt", "ble_relay", "http_long_poll")


def _gen_pairing_code() -> str:
    """生成 8 位字母数字配对码（去掉易混淆字符）"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


class DeviceBinding(Base):
    """设备绑定表"""
    __tablename__ = "device_bindings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pet_avatar_id = Column(BigInteger, ForeignKey("pet_avatars.id", ondelete="CASCADE"), nullable=True, index=True, comment="可空：设备未必绑定到具体分身")

    device_type = Column(String(20), nullable=False, index=True, comment="web/mobile/hologram/desktop_pet/ar_glasses")
    device_id = Column(String(64), nullable=False, comment="设备唯一标识（设备生成或我们颁发）")
    device_name = Column(String(50), nullable=True, comment="用户给设备起的名字")
    capabilities = Column(JSON, nullable=True, comment="设备能力，如 {speech:true, animation:true}")

    pairing_code = Column(String(16), nullable=True, index=True, comment="8位配对码，仅 pending 状态有效")
    pairing_expires_at = Column(DateTime, nullable=True, comment="配对码过期时间")

    transport = Column(String(20), nullable=False, server_default="websocket", comment="传输方式")

    status = Column(String(20), nullable=False, server_default="pending", index=True, comment="pending/online/offline/revoked")
    last_seen_at = Column(DateTime, nullable=True, comment="最近一次心跳时间")
    last_event_at = Column(DateTime, nullable=True, comment="最近一次成功投递事件的时间")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("device_type", "device_id", name="uq_device_type_id"),
        Index("ix_device_bindings_user_status", "user_id", "status"),
    )

    @staticmethod
    def generate_pairing_code() -> str:
        return _gen_pairing_code()

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "pet_avatar_id": self.pet_avatar_id,
            "device_type": self.device_type,
            "device_id": self.device_id,
            "device_name": self.device_name,
            "capabilities": self.capabilities,
            "transport": self.transport,
            "status": self.status,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
