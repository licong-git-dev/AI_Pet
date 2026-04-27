"""
PetPal - MQTT 发布器（桌宠 / 全息设备）

提供一个 async publish(topic, payload) 回调，注入到 Orchestrator。
未启用 MQTT（settings.mqtt_enabled=False 或 paho-mqtt 未安装）时，
publisher 退化为 None，drivers 各自走 mock 路径，不影响主流程。
"""
import json
from typing import Optional, Awaitable, Callable
from loguru import logger

from app.config import settings


_client = None  # paho.mqtt.client.Client | None


def _ensure_client():
    """惰性初始化 paho-mqtt 客户端，失败返回 None。"""
    global _client
    if _client is not None:
        return _client
    if not settings.mqtt_enabled:
        return None
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        logger.warning("[mqtt] paho-mqtt 未安装；MQTT 发布将被禁用")
        return None
    try:
        client_id = f"{settings.mqtt_client_id_prefix}-{id(object()):x}"
        client = mqtt.Client(client_id=client_id, clean_session=True)
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password or "")
        client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=settings.mqtt_keepalive)
        client.loop_start()
        _client = client
        logger.info(f"[mqtt] connected to {settings.mqtt_host}:{settings.mqtt_port}")
        return _client
    except Exception as e:
        logger.warning(f"[mqtt] 连接失败，已禁用：{e}")
        return None


async def publish(topic: str, payload: dict) -> bool:
    """ASP 事件发布到 MQTT。失败返回 False，不抛异常。"""
    client = _ensure_client()
    if client is None:
        return False
    try:
        msg = json.dumps(payload, ensure_ascii=False, default=str)
        info = client.publish(topic, msg, qos=0, retain=False)
        return info.rc == 0
    except Exception as e:
        logger.warning(f"[mqtt] publish failed topic={topic}: {e}")
        return False


def get_publisher() -> Optional[Callable[[str, dict], Awaitable[bool]]]:
    """返回 publisher 回调；MQTT 未启用时返回 None。"""
    if not settings.mqtt_enabled:
        return None
    return publish
