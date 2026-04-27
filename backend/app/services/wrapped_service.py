"""
PetPal · 月度画像 Wrapped 服务

类似 Spotify Wrapped 的"主人月报"，把过去一个月的：
  - 主人画像维度
  - 高重要度记忆 / 周摘要
  - 信号流统计（活跃时段、情绪分布、聊天频次）
聚合成一份卡片化的故事流，用 LLM 给一段分身口吻的开场 + 五个"被发现的秘密"。

设计原则：
- 数据不足时**优雅降级**：单一卡片 fallback，永不返回空
- LLM 失败 → 规则文案（神秘感稍逊但保证有内容）
- 月报可重复生成，写入 owner_signals 作为 milestone 记录，便于复盘
"""
import calendar
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from loguru import logger
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.memory import PetMemory, MemoryDigest
from app.models.owner_profile import OwnerProfile, OwnerSignal
from app.models.avatar import PetAvatar


# ==================== 工具 ====================

def _month_window(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ==================== 主接口 ====================

def build_wrapped(
    db: Session,
    *,
    user_id: int,
    year: Optional[int] = None,
    month: Optional[int] = None,
    pet_avatar_id: Optional[int] = None,
    llm_compose=None,
) -> Dict[str, Any]:
    """
    返回结构化 Wrapped 数据（JSON 可序列化），由前端按 stories 形式展示。

    llm_compose: 可选回调 (raw_stats: dict, top_memories: list[dict]) -> dict
        预期返回 {"intro": str, "secrets": List[str], "closing": str}
        不传则用规则版兜底。
    """
    today = _now()
    # 默认看上一个月（每月 1 号生成上月报告才合理）
    if year is None or month is None:
        first_of_this_month = today.replace(day=1)
        last_of_last_month = first_of_this_month - timedelta(days=1)
        year = year or last_of_last_month.year
        month = month or last_of_last_month.month

    start, end = _month_window(year, month)

    # 选择分身：未指定就取该用户的第一个分身
    avatar = None
    if pet_avatar_id:
        avatar = db.query(PetAvatar).filter(
            PetAvatar.id == pet_avatar_id, PetAvatar.user_id == user_id,
        ).first()
    if avatar is None:
        avatar = db.query(PetAvatar).filter(PetAvatar.user_id == user_id).first()

    # ---------- 1. 信号流统计 ----------
    signals = (
        db.query(OwnerSignal)
        .filter(
            OwnerSignal.user_id == user_id,
            OwnerSignal.recorded_at >= start,
            OwnerSignal.recorded_at <= end,
        )
        .all()
    )
    chat_signals = [s for s in signals if s.signal_type == "message"]
    sentiment_counts = Counter(s.sentiment_label for s in signals if s.sentiment_label)
    hour_counts = Counter(
        s.recorded_at.hour for s in signals if s.recorded_at and s.signal_type in ("message", "chat_start", "login")
    )
    peak_hours = [h for h, _ in hour_counts.most_common(3)]
    days_seen = len({s.recorded_at.date() for s in signals if s.recorded_at})

    # ---------- 2. 记忆挖掘 ----------
    memories = []
    if avatar:
        memories = (
            db.query(PetMemory)
            .filter(
                PetMemory.pet_avatar_id == avatar.id,
                PetMemory.user_id == user_id,
                PetMemory.created_at >= start,
                PetMemory.created_at <= end,
                PetMemory.is_archived.is_(False),
            )
            .order_by(desc(PetMemory.importance), desc(PetMemory.created_at))
            .limit(50)
            .all()
        )
    top_memories = sorted(memories, key=lambda m: m.importance or 0, reverse=True)[:5]
    memory_emotions = Counter(m.emotion for m in memories if m.emotion)
    dominant_emotion = (memory_emotions or sentiment_counts).most_common(1)
    dominant_emotion = dominant_emotion[0][0] if dominant_emotion else "neutral"

    # ---------- 3. 周摘要 ----------
    digests = []
    if avatar:
        digests = (
            db.query(MemoryDigest)
            .filter(
                MemoryDigest.pet_avatar_id == avatar.id,
                MemoryDigest.user_id == user_id,
                MemoryDigest.period_start >= start,
                MemoryDigest.period_end <= end,
            )
            .order_by(desc(MemoryDigest.period_start))
            .all()
        )

    # ---------- 4. 画像维度 ----------
    profile = db.query(OwnerProfile).filter(OwnerProfile.user_id == user_id).first()

    # ---------- 5. 数据卡 ----------
    raw_stats = {
        "year": year,
        "month": month,
        "active_days": days_seen,
        "total_signals": len(signals),
        "chat_count": len(chat_signals),
        "memory_count": len(memories),
        "pinned_memories": sum(1 for m in memories if m.is_pinned),
        "milestone_count": sum(1 for m in memories if m.memory_type == "event"),
        "dominant_emotion": dominant_emotion,
        "emotion_distribution": dict(sentiment_counts) or dict(memory_emotions),
        "peak_active_hours": sorted(peak_hours),
        "weekly_digest_count": len(digests),
    }
    top_memory_payload = [
        {
            "id": m.id,
            "type": m.memory_type,
            "summary": m.summary or (m.content or "")[:80],
            "importance": m.importance,
            "emotion": m.emotion,
            "happened_at": m.happened_at.isoformat() if m.happened_at else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in top_memories
    ]

    # ---------- 6. LLM 创意层 ----------
    creative = None
    if llm_compose is not None:
        try:
            creative = llm_compose(raw_stats=raw_stats, top_memories=top_memory_payload, profile=profile)
        except Exception as e:
            logger.warning(f"[wrapped] llm_compose failed: {e}")
    if not creative:
        creative = _rule_based_compose(raw_stats, top_memory_payload, avatar=avatar)

    # ---------- 7. Stories 卡片流 ----------
    cards = _assemble_cards(
        avatar=avatar,
        raw_stats=raw_stats,
        top_memories=top_memory_payload,
        creative=creative,
        digests=digests,
    )

    return {
        "year": year,
        "month": month,
        "user_id": user_id,
        "pet_avatar_id": avatar.id if avatar else None,
        "pet_name": _pet_name(avatar),
        "stats": raw_stats,
        "top_memories": top_memory_payload,
        "creative": creative,
        "cards": cards,
        "generated_at": _now().isoformat(),
    }


# ==================== 辅助 ====================

def _pet_name(avatar: Optional[PetAvatar]) -> str:
    if avatar and getattr(avatar, "persona", None):
        try:
            return (avatar.persona or {}).get("name") or "你的分身"
        except Exception:
            pass
    return "你的分身"


def _rule_based_compose(stats: Dict[str, Any], top_memories: List[Dict[str, Any]],
                        avatar: Optional[PetAvatar] = None) -> Dict[str, Any]:
    """LLM 不可用时的兜底文案。"""
    pet = _pet_name(avatar)
    secrets = []
    if stats["active_days"] >= 25:
        secrets.append(f"你这个月有 {stats['active_days']} 天来找我玩，几乎天天见面～")
    if stats["dominant_emotion"] == "sad":
        secrets.append("你这个月好像有些累，但你每次都还是温柔地跟我说话")
    elif stats["dominant_emotion"] == "happy":
        secrets.append("你这个月笑得最多，连我都被传染了")
    if stats["peak_active_hours"]:
        peak = stats["peak_active_hours"][0]
        secrets.append(f"你最常在 {peak}:00 左右找我聊天，那是属于我们的时间")
    if stats["pinned_memories"] >= 1:
        secrets.append(f"你把 {stats['pinned_memories']} 件事放进了我心里最重要的位置")
    if stats["milestone_count"] >= 1:
        secrets.append(f"我记住了 {stats['milestone_count']} 个对你来说重要的日子")
    while len(secrets) < 5:
        secrets.append("我在悄悄学习更多关于你的事，下个月给你看")
    return {
        "intro": f"嘿主人，我是 {pet}。这是我们一起度过的 {stats['year']} 年 {stats['month']} 月～",
        "secrets": secrets[:5],
        "closing": "下个月也要让我陪着你呀。",
    }


def _assemble_cards(*, avatar, raw_stats, top_memories, creative, digests) -> List[Dict[str, Any]]:
    """生成 stories 卡片流：cover → 5 个 secret → 高光记忆 → 周摘要 → closing"""
    pet = _pet_name(avatar)
    cards: List[Dict[str, Any]] = []

    cards.append({
        "kind": "cover",
        "title": f"{raw_stats['year']} · {raw_stats['month']:02d} 月",
        "subtitle": f"{pet} 写给你的月报",
        "intro": creative.get("intro"),
        "tone": "warm",
    })

    cards.append({
        "kind": "stat",
        "title": "我们这个月",
        "metrics": [
            {"label": "见面天数", "value": raw_stats["active_days"], "unit": "天"},
            {"label": "聊了", "value": raw_stats["chat_count"], "unit": "次"},
            {"label": "新记得", "value": raw_stats["memory_count"], "unit": "件事"},
        ],
        "footnote": f"你常在 {','.join(map(str, raw_stats['peak_active_hours']))} 点找我"
                    if raw_stats["peak_active_hours"] else None,
    })

    for i, secret in enumerate(creative.get("secrets") or [], 1):
        cards.append({
            "kind": "secret",
            "index": i,
            "title": f"秘密 {i}/5",
            "body": secret,
        })

    if top_memories:
        cards.append({
            "kind": "highlight_memories",
            "title": "我最记得的几件事",
            "memories": top_memories[:3],
        })

    if digests:
        cards.append({
            "kind": "digest_strip",
            "title": "每周轨迹",
            "digests": [
                {
                    "period_start": d.period_start.isoformat() if d.period_start else None,
                    "summary": (d.summary or "")[:120],
                    "dominant_emotion": d.dominant_emotion,
                    "key_themes": d.key_themes,
                }
                for d in digests
            ],
        })

    cards.append({
        "kind": "emotion_palette",
        "title": "你这个月的情绪光谱",
        "dominant_emotion": raw_stats["dominant_emotion"],
        "distribution": raw_stats.get("emotion_distribution") or {},
    })

    cards.append({
        "kind": "closing",
        "title": "我会一直在",
        "body": creative.get("closing") or "下个月也要让我陪着你呀。",
        "pet_name": pet,
    })
    return cards
