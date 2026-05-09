"""
集成测试：GET /api/v1/owner-profile/wrapped
- 鉴权
- 空数据：仍然返回完整 cards 结构 + 5 条规则版 secrets
- 信号 + 记忆构造后：peak_active_hours / 高光记忆 / dominant_emotion 出现在 stats
- 显式 year/month 起作用
"""
from datetime import datetime

API = "/api/v1/owner-profile/wrapped"


def test_wrapped_requires_auth(client):
    assert client.get(API).status_code == 401


def test_wrapped_empty_user_returns_fallback(client, auth_headers):
    r = client.get(API, headers=auth_headers, params={"year": 2026, "month": 4})
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["year"] == 2026 and body["month"] == 4
    assert body["stats"]["total_signals"] == 0
    kinds = [c["kind"] for c in body["cards"]]
    assert "cover" in kinds and "closing" in kinds
    # 规则兜底必须给 5 条
    assert len(body["creative"]["secrets"]) == 5


def test_wrapped_with_data(client, auth_headers, db_factory, seeded):
    """先种几条 OwnerSignal + PetMemory，再调 wrapped 看聚合是否生效。"""
    from app.models.owner_profile import OwnerSignal
    from app.models.memory import PetMemory

    s = db_factory()
    try:
        base = datetime(2026, 4, 10, 22, 0, 0)
        for i in range(8):
            s.add(OwnerSignal(
                user_id=seeded["user_id"],
                signal_type="message",
                payload={"length": 30 + i},
                sentiment_label="happy" if i % 2 == 0 else "sad",
                sentiment_score=0.4 if i % 2 == 0 else -0.3,
                text_excerpt=f"对话 {i}",
                recorded_at=base.replace(hour=21 + (i % 3)),
            ))
        for content, imp, emo, t in [
            ("领养纪念日", 10, "loving", "event"),
            ("加班崩溃", 8, "anxious", "episodic"),
        ]:
            m = PetMemory(
                pet_avatar_id=seeded["avatar_id"], user_id=seeded["user_id"],
                content=content, summary=content, importance=imp, emotion=emo,
                memory_type=t, source="conversation",
            )
            m.created_at = base
            m.happened_at = base
            s.add(m)
        s.commit()
    finally:
        s.close()

    r = client.get(API, headers=auth_headers,
                   params={"year": 2026, "month": 4,
                           "pet_avatar_id": seeded["avatar_id"]})
    assert r.status_code == 200
    body = r.json()["data"]
    stats = body["stats"]
    assert stats["chat_count"] == 8
    assert stats["memory_count"] == 2
    assert stats["milestone_count"] == 1
    assert isinstance(stats["peak_active_hours"], list) and stats["peak_active_hours"]
    # 卡片流应包含高光记忆 / 情绪光谱
    kinds = {c["kind"] for c in body["cards"]}
    assert "highlight_memories" in kinds
    assert "emotion_palette" in kinds
    # top_memories 第一条应是 importance=10 的领养纪念日
    assert body["top_memories"][0]["importance"] == 10
