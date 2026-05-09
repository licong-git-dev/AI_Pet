"""
集成测试：/api/v1/memory/* 的核心路径
- 鉴权拦截
- 创建 → 列表 → 置顶 → 归档 → 删除
- 不同 avatar 之间的隔离
- 花园统计
"""

API = "/api/v1/memory"


def test_memory_endpoints_require_auth(client):
    assert client.get(f"{API}/list?avatar_id=1").status_code == 401
    assert client.post(API, json={}).status_code == 401


def test_create_then_list_and_pin_then_archive_then_delete(client, auth_headers, seeded):
    avatar_id = seeded["avatar_id"]

    # 1. 创建
    r = client.post(API, headers=auth_headers, json={
        "pet_avatar_id": avatar_id,
        "memory_type": "episodic",
        "content": "今天主人给我换了新猫粮，超级香",
        "importance": 7,
        "emotion": "happy",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == 0
    mid = body["data"]["id"]
    assert mid > 0

    # 2. 列表能看到
    r = client.get(f"{API}/list", headers=auth_headers, params={"avatar_id": avatar_id})
    assert r.status_code == 200
    data = r.json()["data"]
    assert any(m["id"] == mid for m in data)

    # 3. 置顶 → 再列表 → 第一条应该是它
    r = client.post(f"{API}/{mid}/pin", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["is_pinned"] is True

    r = client.get(f"{API}/list", headers=auth_headers, params={"avatar_id": avatar_id})
    assert r.json()["data"][0]["id"] == mid

    # 4. 归档
    r = client.patch(f"{API}/{mid}", headers=auth_headers, json={"is_archived": True})
    assert r.status_code == 200
    assert r.json()["data"]["is_archived"] is True

    # 默认不含归档
    r = client.get(f"{API}/list", headers=auth_headers, params={"avatar_id": avatar_id})
    assert all(m["id"] != mid for m in r.json()["data"])

    # include_archived=true 又能看到
    r = client.get(f"{API}/list", headers=auth_headers,
                   params={"avatar_id": avatar_id, "include_archived": True})
    assert any(m["id"] == mid for m in r.json()["data"])

    # 5. 删除
    r = client.delete(f"{API}/{mid}", headers=auth_headers)
    assert r.status_code == 200
    r = client.get(f"{API}/list", headers=auth_headers,
                   params={"avatar_id": avatar_id, "include_archived": True})
    assert all(m["id"] != mid for m in r.json()["data"])


def test_garden_stats_aggregates_after_writes(client, auth_headers, seeded):
    avatar_id = seeded["avatar_id"]
    for emo, t in [("happy", "episodic"), ("sad", "episodic"), ("loving", "preference")]:
        client.post(API, headers=auth_headers, json={
            "pet_avatar_id": avatar_id,
            "content": f"测试-{emo}",
            "memory_type": t, "importance": 6, "emotion": emo,
        })
    r = client.get(f"{API}/garden/{avatar_id}", headers=auth_headers)
    assert r.status_code == 200
    s = r.json()["data"]
    assert s["total"] == 3
    assert s["by_type"]["episodic"] == 2
    assert s["by_type"]["preference"] == 1
    assert s["by_emotion"]["happy"] == 1


def test_cannot_access_other_users_avatar(client, auth_headers, db_factory):
    """另造一个用户 + 分身；当前 token 不应该能写入它的记忆。"""
    from app.models.user import User
    from app.models.pet import Pet
    from app.models.avatar import PetAvatar
    s = db_factory()
    try:
        u2 = User(phone="13900000002", nickname="别人", password="x")
        s.add(u2); s.flush()
        p2 = Pet(owner_id=u2.id, name="阿黄", pet_type="dog")
        s.add(p2); s.flush()
        a2 = PetAvatar(pet_id=p2.id, user_id=u2.id, speaking_style="cute")
        s.add(a2); s.commit()
        other_avatar_id = a2.id
    finally:
        s.close()

    r = client.post(API, headers=auth_headers, json={
        "pet_avatar_id": other_avatar_id,
        "content": "应该写不进去",
        "importance": 5,
    })
    # api/memory.py 的 _ensure_avatar_owned 抛 404
    assert r.status_code == 404
