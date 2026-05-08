"""
PetPal · wrapped_service 单测

覆盖：
- 空数据：cards 仍 ≥ closing 数量，5 个 secrets 走规则兜底
- 中等数据：含统计 + 高光记忆 + 情绪光谱
- LLM compose 注入：返回值能进入 cards
"""
from datetime import datetime, timedelta

from app.services import wrapped_service
from app.services import memory_service


def _seed_signals(db_session, user_id, n_chat=10, n_login=5, year=None, month=None):
    """造一批 OwnerSignal 给 wrapped_service 用。"""
    from app.models.owner_profile import OwnerSignal
    if year is None or month is None:
        # 默认放在当月
        now = datetime.utcnow()
        year, month = now.year, now.month
    base = datetime(year, month, 5, 22, 0, 0)
    for i in range(n_chat):
        db_session.add(OwnerSignal(
            user_id=user_id,
            signal_type="message",
            payload={"length": 25 + i},
            sentiment_score=0.4 if i % 2 == 0 else -0.2,
            sentiment_label="happy" if i % 2 == 0 else "sad",
            text_excerpt=f"对话片段 {i}",
            recorded_at=base + timedelta(hours=i),
        ))
    for i in range(n_login):
        db_session.add(OwnerSignal(
            user_id=user_id,
            signal_type="login",
            recorded_at=base + timedelta(days=i),
        ))
    db_session.commit()


def test_wrapped_empty_user_returns_fallback(db_session, seed_user):
    """完全没数据的用户也能拿到月报，stats=0、cards 至少含 cover/closing。"""
    out = wrapped_service.build_wrapped(
        db_session,
        user_id=seed_user.id,
        year=2026, month=4,
    )
    assert out["year"] == 2026 and out["month"] == 4
    assert out["stats"]["total_signals"] == 0
    assert out["stats"]["chat_count"] == 0
    kinds = [c["kind"] for c in out["cards"]]
    assert "cover" in kinds
    assert "closing" in kinds
    # 兜底 secrets 至少 5 条
    assert len(out["creative"]["secrets"]) == 5


def test_wrapped_with_signals_and_memories(db_session, seed_pet_avatar):
    user_id = seed_pet_avatar.user_id
    _seed_signals(db_session, user_id=user_id, n_chat=12, n_login=4, year=2026, month=4)
    # 时间戳在 4 月的记忆
    base = datetime(2026, 4, 10, 21, 0, 0)
    for content, imp, emo in [
        ("领养纪念日庆祝", 10, "loving"),
        ("主人加班至深夜", 8, "anxious"),
        ("散步遇到老朋友", 6, "happy"),
    ]:
        m = memory_service.write_memory(
            db_session,
            pet_avatar_id=seed_pet_avatar.id, user_id=user_id,
            content=content, importance=imp, emotion=emo,
            memory_type="event" if imp >= 9 else "episodic",
        )
        m.created_at = base
        m.happened_at = base
    db_session.commit()

    out = wrapped_service.build_wrapped(
        db_session, user_id=user_id, year=2026, month=4,
        pet_avatar_id=seed_pet_avatar.id,
    )

    s = out["stats"]
    assert s["chat_count"] >= 1
    assert s["memory_count"] == 3
    assert s["milestone_count"] == 1  # event 类型计入里程碑
    assert isinstance(s["peak_active_hours"], list) and s["peak_active_hours"]

    kinds = [c["kind"] for c in out["cards"]]
    assert "cover" in kinds and "closing" in kinds
    assert "stat" in kinds
    assert "highlight_memories" in kinds
    assert "emotion_palette" in kinds

    # top_memories 应按 importance 降序，第 1 条是领养纪念日
    assert out["top_memories"][0]["summary"]
    assert out["top_memories"][0]["importance"] == 10


def test_wrapped_llm_compose_injected(db_session, seed_pet_avatar):
    """显式提供 llm_compose 回调时，secrets 来自回调而非规则版。"""
    _seed_signals(db_session, user_id=seed_pet_avatar.user_id, n_chat=6, year=2026, month=3)

    def fake_compose(*, raw_stats, top_memories, profile=None):
        return {
            "intro": "嘿主人，是我！",
            "secrets": ["秘密 A", "秘密 B", "秘密 C", "秘密 D", "秘密 E"],
            "closing": "下个月见～",
        }

    out = wrapped_service.build_wrapped(
        db_session,
        user_id=seed_pet_avatar.user_id, year=2026, month=3,
        pet_avatar_id=seed_pet_avatar.id,
        llm_compose=fake_compose,
    )
    assert out["creative"]["intro"] == "嘿主人，是我！"
    assert out["creative"]["secrets"][0] == "秘密 A"


def test_wrapped_llm_compose_failure_falls_back(db_session, seed_pet_avatar):
    """llm_compose 抛异常时，应回退到规则版而不是返回 500。"""
    _seed_signals(db_session, user_id=seed_pet_avatar.user_id, n_chat=4)

    def boom(**kw):
        raise RuntimeError("LLM down")

    out = wrapped_service.build_wrapped(
        db_session, user_id=seed_pet_avatar.user_id,
        pet_avatar_id=seed_pet_avatar.id,
        llm_compose=boom,
    )
    # 规则版兜底总是 5 条
    assert len(out["creative"]["secrets"]) == 5
