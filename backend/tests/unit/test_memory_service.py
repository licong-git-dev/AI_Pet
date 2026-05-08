"""
PetPal · memory_service 单测

覆盖：
- 写入 / 字段持久化
- 规则版抽取的三种判定（trivial / 强情感 / 里程碑）
- 检索打分（关键词命中 + 重要度 + 置顶）
- 衰减扫描（过期非置顶 → 归档）
- 周摘要（rule-based 兜底）
- garden_stats 聚合
"""
from datetime import datetime, timedelta

import pytest

from app.services import memory_service
from app.models.memory import PetMemory


# ==================== 写入 + 持久化 ====================

def test_write_memory_persists_fields(db_session, seed_pet_avatar):
    avatar = seed_pet_avatar
    mem = memory_service.write_memory(
        db_session,
        pet_avatar_id=avatar.id,
        user_id=avatar.user_id,
        content="主人今天加班到深夜",
        memory_type="episodic",
        importance=8,
        emotion="sad",
        emotion_intensity=0.7,
        source="conversation",
    )
    db_session.commit()
    db_session.refresh(mem)
    assert mem.id is not None
    assert mem.importance == 8
    assert mem.emotion == "sad"
    assert mem.memory_type == "episodic"
    assert mem.summary  # 自动生成
    assert mem.effective_strength == pytest.approx(0.8, abs=0.01)


def test_write_memory_clamps_importance(db_session, seed_pet_avatar):
    mem = memory_service.write_memory(
        db_session, pet_avatar_id=seed_pet_avatar.id, user_id=seed_pet_avatar.user_id,
        content="x", importance=99,
    )
    assert mem.importance == 10
    mem2 = memory_service.write_memory(
        db_session, pet_avatar_id=seed_pet_avatar.id, user_id=seed_pet_avatar.user_id,
        content="y", importance=-5,
    )
    assert mem2.importance == 0


# ==================== 规则版抽取 ====================

def test_extract_trivial_returns_none():
    out = memory_service.extract_memory_from_message(
        user_message="嗨", assistant_message="喵～",
    )
    assert out is None


def test_extract_strong_negative_kept_with_high_importance():
    out = memory_service.extract_memory_from_message(
        user_message="今天压力好大，崩溃了",
        assistant_message="*蹭蹭你*",
    )
    assert out is not None
    assert out["importance"] >= 8
    assert out["emotion"] == "sad"


def test_extract_milestone_returns_event_type():
    out = memory_service.extract_memory_from_message(
        user_message="今天是豆包的领养纪念日！",
        assistant_message="!",
    )
    assert out is not None
    assert out["memory_type"] == "event"
    assert out["importance"] >= 9


# ==================== 检索打分 ====================

def test_retrieve_prefers_keyword_match(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                content="主人喜欢爬山", importance=5)
    memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                content="主人养了一盆绿萝", importance=5)
    db_session.commit()
    top = memory_service.retrieve_memories(
        db_session, pet_avatar_id=a.id, user_id=a.user_id,
        query="主人 爬山", top_k=2,
    )
    assert top
    assert "爬山" in top[0].content


def test_retrieve_pinned_wins(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    common = memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                         content="路过宠物店", importance=3)
    pinned = memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                         content="主人爱吃寿司", importance=3)
    pinned.is_pinned = True
    db_session.commit()
    top = memory_service.retrieve_memories(
        db_session, pet_avatar_id=a.id, user_id=a.user_id,
        query="完全无关的查询关键词", top_k=2,
    )
    assert top[0].id == pinned.id  # 置顶在前


def test_retrieve_increments_recall_count(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    m = memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                    content="重要的一天", importance=8)
    db_session.commit()
    before = m.recall_count or 0
    memory_service.retrieve_memories(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                     query="重要", top_k=5)
    db_session.refresh(m)
    assert m.recall_count == before + 1
    assert m.last_recalled_at is not None


# ==================== 衰减 ====================

def test_decay_archives_old_low_importance(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    old = memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                      content="无关紧要的事", importance=1)
    # 模拟很久之前
    old.created_at = datetime.utcnow() - timedelta(days=400)
    old.last_recalled_at = old.created_at
    db_session.commit()
    res = memory_service.decay_pass(db_session)
    db_session.refresh(old)
    assert res["archived"] >= 1
    assert old.is_archived is True


def test_decay_keeps_pinned(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    m = memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                    content="纪念日", importance=2)
    m.created_at = datetime.utcnow() - timedelta(days=1000)
    m.is_pinned = True
    db_session.commit()
    memory_service.decay_pass(db_session)
    db_session.refresh(m)
    assert m.is_archived is False
    assert m.effective_strength == 1.0  # 置顶强度恒为 1


def test_decay_skips_preference_type(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    m = memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                    content="主人喜欢叫我豆包", importance=2,
                                    memory_type="preference")
    m.created_at = datetime.utcnow() - timedelta(days=1000)
    m.last_recalled_at = m.created_at
    db_session.commit()
    memory_service.decay_pass(db_session)
    db_session.refresh(m)
    assert m.is_archived is False  # preference 永不归档


# ==================== 周摘要（规则兜底） ====================

def test_weekly_digest_rule_based(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    for content, emo in [
        ("加班到很晚", "anxious"),
        ("和朋友聚会很开心", "happy"),
        ("散步看到流浪猫", "neutral"),
    ]:
        memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                    content=content, importance=6, emotion=emo)
    db_session.commit()
    digest = memory_service.build_weekly_digest(db_session,
                                                pet_avatar_id=a.id, user_id=a.user_id)
    db_session.commit()
    assert digest is not None
    assert digest.summary
    assert digest.dominant_emotion in ("anxious", "happy", "neutral")
    assert digest.period_type == "weekly"


def test_weekly_digest_too_few_returns_none(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                content="孤零零的一条", importance=5)
    db_session.commit()
    digest = memory_service.build_weekly_digest(db_session,
                                                pet_avatar_id=a.id, user_id=a.user_id)
    assert digest is None  # 少于 3 条不出摘要


# ==================== 花园统计 ====================

def test_garden_stats_aggregates(db_session, seed_pet_avatar):
    a = seed_pet_avatar
    memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                content="x", emotion="happy", importance=5)
    m = memory_service.write_memory(db_session, pet_avatar_id=a.id, user_id=a.user_id,
                                    content="y", emotion="sad", importance=8,
                                    memory_type="event")
    m.is_pinned = True
    db_session.commit()
    stats = memory_service.garden_stats(db_session, pet_avatar_id=a.id, user_id=a.user_id)
    assert stats["total"] == 2
    assert stats["pinned_count"] == 1
    assert stats["by_emotion"].get("happy") == 1
    assert stats["by_type"].get("event") == 1
    assert stats["by_type"].get("episodic") == 1
