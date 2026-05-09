"""
集成测试：/api/v1/devices/* 配对码闭环
- pair/start：设备拿到 8 位配对码 + binding_id
- pair/confirm：主人输入配对码完成绑定
- heartbeat：心跳保活
- /me：列出已绑定设备
- /revoke：解绑
- 错误码：过期 / 不存在 / 不属于自己
"""
from datetime import datetime, timedelta

API = "/api/v1/devices"


def test_pair_start_no_auth_required(client):
    """设备侧调 start 不需要登录"""
    r = client.post(f"{API}/pair/start", json={
        "device_type": "desktop_pet",
        "device_id": "raspi-001",
        "device_name": "客厅小桌宠",
        "transport": "mqtt",
    })
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["pairing_code"]
    assert len(body["pairing_code"]) == 8
    assert body["binding_id"] > 0


def test_full_pairing_flow(client, auth_headers, seeded):
    # 1. 设备 start
    r = client.post(f"{API}/pair/start", json={
        "device_type": "desktop_pet",
        "device_id": "raspi-flow-1",
        "device_name": "测试桌宠",
    })
    assert r.status_code == 200
    code = r.json()["data"]["pairing_code"]
    binding_id = r.json()["data"]["binding_id"]

    # 2. 主人 confirm
    r = client.post(f"{API}/pair/confirm", headers=auth_headers, json={
        "pairing_code": code,
        "pet_avatar_id": seeded["avatar_id"],
        "device_name": "我的桌宠",
    })
    assert r.status_code == 200, r.text
    bound = r.json()["data"]
    assert bound["status"] == "online"
    assert bound["pet_avatar_id"] == seeded["avatar_id"]

    # 3. 心跳
    r = client.post(f"{API}/heartbeat", json={"binding_id": binding_id})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "online"

    # 4. /me 列表能看到
    r = client.get(f"{API}/me", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == binding_id

    # 5. revoke
    r = client.post(f"{API}/{binding_id}/revoke", headers=auth_headers)
    assert r.status_code == 200

    # /me 不再列出
    r = client.get(f"{API}/me", headers=auth_headers)
    assert r.json()["data"] == []


def test_confirm_with_bad_code_returns_404(client, auth_headers):
    r = client.post(f"{API}/pair/confirm", headers=auth_headers,
                    json={"pairing_code": "ZZZZZZZZ"})
    assert r.status_code == 404


def test_confirm_with_expired_code_returns_410(client, auth_headers, db_factory):
    """直接造一个 pending 但已过期的 binding，测过期分支。"""
    from app.models.device import DeviceBinding
    s = db_factory()
    try:
        b = DeviceBinding(
            user_id=0,
            device_type="desktop_pet",
            device_id="raspi-expired",
            pairing_code="EXPIRED1",
            pairing_expires_at=datetime.utcnow() - timedelta(minutes=1),
            status="pending",
        )
        s.add(b); s.commit()
    finally:
        s.close()

    r = client.post(f"{API}/pair/confirm", headers=auth_headers,
                    json={"pairing_code": "EXPIRED1"})
    assert r.status_code == 410


def test_heartbeat_for_unknown_binding_returns_404(client):
    r = client.post(f"{API}/heartbeat", json={"binding_id": 999999})
    assert r.status_code == 404
