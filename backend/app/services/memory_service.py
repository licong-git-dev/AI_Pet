"""
PetPal - 长期记忆服务

核心能力：
- write(): 写入一条记忆（来自对话 / 手动 / 观察 / 周期总结）
- retrieve(): 给定查询，混合排序检索 top-K 记忆
- decay(): 每日批量更新有效强度，触发归档
- weekly_digest(): 把过去一周的 episodic 蒸馏为 semantic 记忆

实现要点（v1）：
- 向量检索暂用 LIKE + LLM 重排兜底；预留 embedding_vector_id 字段
- 遗忘曲线：effective_strength = importance/10 * exp(-days_since_recall / TAU)
- 写入由 LLM 提取，本服务保留"规则提取"作为 LLM 不可用时的兜底

参考：docs/PRODUCT_DESIGN.md §1
"""
import math
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from loguru import logger
from sqlalchemy import or_, and_, desc, func
from sqlalchemy.orm import Session

from app.models.memory import PetMemory, MemoryDigest


# ==================== 衰减参数 ====================

TAU_DAYS = 30.0  # 衰减时间常数（30 天后强度降到约 37%）
ARCHIVE_THRESHOLD = 0.05
"""低于该有效强度的非置顶记忆被归档"""

# 检索打分权重
W_RELEVANCE = 0.40
W_RECENCY = 0.20
W_IMPORTANCE = 0.25
W_EMOTION = 0.15


# ==================== 工具 ====================

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _days_since(ts: Optional[datetime]) -> float:
    if ts is None:
        return 0.0
    return max(0.0, (_now() - ts).total_seconds() / 86400.0)


def _calc_effective_strength(memory: PetMemory) -> float:
    """艾宾浩斯式：强度 = 重要度归一 × exp(-过去天数 / τ)"""
    if memory.is_pinned:
        return 1.0
    base = (memory.importance or 5) / 10.0
    last = memory.last_recalled_at or memory.created_at or _now()
    days = _days_since(last)
    return round(base * math.exp(-days / TAU_DAYS), 4)


# ==================== 写入 ====================

def write_memory(
    db: Session,
    *,
    pet_avatar_id: int,
    user_id: int,
    content: str,
    memory_type: str = "episodic",
    summary: Optional[str] = None,
    importance: int = 5,
    emotion: Optional[str] = None,
    emotion_intensity: Optional[float] = None,
    source: str = "conversation",
    source_ref: Optional[str] = None,
    happened_at: Optional[datetime] = None,
) -> PetMemory:
    """写入单条记忆，自动计算初始 effective_strength。"""
    importance = max(0, min(10, int(importance)))
    mem = PetMemory(
        pet_avatar_id=pet_avatar_id,
        user_id=user_id,
        memory_type=memory_type,
        content=content,
        summary=summary or content[:120],
        importance=importance,
        emotion=emotion,
        emotion_intensity=emotion_intensity,
        source=source,
        source_ref=source_ref,
        happened_at=happened_at or _now(),
        effective_strength=importance / 10.0,
    )
    db.add(mem)
    db.flush()
    logger.info(f"[memory] write avatar={pet_avatar_id} type={memory_type} importance={importance} id={mem.id}")
    return mem


async def extract_memory_from_message_llm(
    *, user_message: str, assistant_message: str
) -> Optional[Dict[str, Any]]:
    """
    LLM 版"对话→记忆"抽取。
    优先调用配置的 LLM，失败时自动降级到规则版。
    返回 None 表示不值得形成长期记忆（LLM 显式 keep=false 或规则未触发）。
    """
    try:
        from app.services.llm import get_llm, prompts
        llm = get_llm()
        if not getattr(llm, "is_available", False):
            return extract_memory_from_message(
                user_message=user_message, assistant_message=assistant_message
            )
        msgs = prompts.extract_memory_messages(user_message, assistant_message)
        data = await llm.complete_json(msgs, temperature=0.2)
        if not data.get("keep"):
            return None
        # 校验并归一化字段
        importance = max(0, min(10, int(data.get("importance", 5))))
        emotion = data.get("emotion") or "neutral"
        intensity = data.get("emotion_intensity")
        try:
            intensity = max(0.0, min(1.0, float(intensity))) if intensity is not None else None
        except (TypeError, ValueError):
            intensity = None
        memory_type = data.get("memory_type") or "episodic"
        if memory_type not in ("episodic", "semantic", "preference", "event"):
            memory_type = "episodic"
        content = (data.get("content") or user_message)[:2000]
        summary = (data.get("summary") or content)[:120]
        return {
            "memory_type": memory_type,
            "content": content,
            "summary": summary,
            "importance": importance,
            "emotion": emotion,
            "emotion_intensity": intensity,
        }
    except Exception as e:
        logger.warning(f"[memory] LLM 抽取失败，降级到规则版: {e}")
        return extract_memory_from_message(
            user_message=user_message, assistant_message=assistant_message
        )


def extract_memory_from_message(
    *, user_message: str, assistant_message: str
) -> Optional[Dict[str, Any]]:
    """
    规则兜底版的"对话→记忆"抽取。
    LLM 不可用时使用此函数。
    返回 None 表示这次对话不值得形成长期记忆。
    """
    text = (user_message or "").strip()
    if not text or len(text) < 6:
        return None

    # 强情感触发词 → 高重要度
    strong_positive = ("爱你", "想你", "最棒", "开心死了", "太幸福")
    strong_negative = ("难过", "崩溃", "伤心", "哭了", "好累", "压力好大")
    milestones = ("生日", "纪念日", "搬家", "第一次", "结婚", "毕业", "离职", "入职")

    importance = 4
    emotion = "neutral"
    intensity = 0.3

    for kw in strong_positive:
        if kw in text:
            importance = max(importance, 8)
            emotion = "loving"
            intensity = 0.85
    for kw in strong_negative:
        if kw in text:
            importance = max(importance, 8)
            emotion = "sad"
            intensity = 0.85
    for kw in milestones:
        if kw in text:
            importance = max(importance, 9)
            return {
                "memory_type": "event",
                "content": text,
                "summary": text[:120],
                "importance": importance,
                "emotion": emotion,
                "emotion_intensity": intensity,
            }

    if importance < 6:
        return None  # 平淡对话不值得记

    return {
        "memory_type": "episodic",
        "content": text,
        "summary": text[:120],
        "importance": importance,
        "emotion": emotion,
        "emotion_intensity": intensity,
    }


# ==================== 检索 ====================

def retrieve_memories(
    db: Session,
    *,
    pet_avatar_id: int,
    user_id: int,
    query: str,
    top_k: int = 5,
    include_archived: bool = False,
) -> List[PetMemory]:
    """
    混合排序检索 top-K 记忆。

    v1 用关键词命中 + 重要度 + 新鲜度 + 情感强度组合打分。
    后续可在此函数内替换为向量检索而不改外部接口。
    """
    q = db.query(PetMemory).filter(
        PetMemory.pet_avatar_id == pet_avatar_id,
        PetMemory.user_id == user_id,
    )
    if not include_archived:
        q = q.filter(PetMemory.is_archived.is_(False))

    # 简单关键词召回（v1）
    keywords = [k for k in query.split() if len(k) >= 2]
    candidates: List[PetMemory] = []
    if keywords:
        like_filters = [PetMemory.content.like(f"%{k}%") for k in keywords]
        candidates = q.filter(or_(*like_filters)).limit(50).all()
    # 兜底：取最近 / 高重要度的备选
    if len(candidates) < top_k:
        more = q.order_by(
            desc(PetMemory.is_pinned),
            desc(PetMemory.importance),
            desc(PetMemory.created_at),
        ).limit(top_k * 4).all()
        seen = {m.id for m in candidates}
        for m in more:
            if m.id not in seen:
                candidates.append(m)
                if len(candidates) >= top_k * 4:
                    break

    # 打分 & 排序
    scored = [(m, _score(m, query, keywords)) for m in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [m for m, _ in scored[:top_k]]

    # 标记召回（异步更可，但 v1 同步即可）
    if top:
        now = _now()
        for m in top:
            m.last_recalled_at = now
            m.recall_count = (m.recall_count or 0) + 1
        db.flush()

    return top


def _score(mem: PetMemory, query: str, keywords: List[str]) -> float:
    relevance = 0.0
    if keywords:
        hits = sum(1 for k in keywords if k in (mem.content or ""))
        relevance = min(1.0, hits / max(1, len(keywords)))
    elif query and query in (mem.content or ""):
        relevance = 0.5

    days_old = _days_since(mem.created_at)
    recency = math.exp(-days_old / TAU_DAYS)
    importance = (mem.importance or 5) / 10.0
    emo = mem.emotion_intensity or 0.0

    score = (
        W_RELEVANCE * relevance
        + W_RECENCY * recency
        + W_IMPORTANCE * importance
        + W_EMOTION * emo
    )
    if mem.is_pinned:
        score += 0.5
    return score


def format_memories_for_prompt(memories: List[PetMemory]) -> str:
    """把检索结果格式化成喂给 LLM 的上下文片段。"""
    if not memories:
        return ""
    lines = ["以下是你（宠物分身）记得的关于主人的事："]
    for i, m in enumerate(memories, 1):
        tag = m.memory_type
        when = (m.happened_at or m.created_at).strftime("%Y-%m-%d") if (m.happened_at or m.created_at) else ""
        lines.append(f"{i}. [{tag}|{when}] {m.summary or m.content[:120]}")
    return "\n".join(lines)


# ==================== 衰减 / 归档 ====================

def decay_pass(db: Session, batch_size: int = 500) -> Dict[str, int]:
    """
    批量更新所有未归档记忆的 effective_strength；
    将低于阈值的非置顶记忆归档。

    通常由 Celery 每日任务调用。
    """
    updated = 0
    archived = 0
    offset = 0
    while True:
        chunk = (
            db.query(PetMemory)
            .filter(PetMemory.is_archived.is_(False))
            .order_by(PetMemory.id)
            .offset(offset)
            .limit(batch_size)
            .all()
        )
        if not chunk:
            break
        for m in chunk:
            new_strength = _calc_effective_strength(m)
            if abs((m.effective_strength or 0) - new_strength) > 1e-3:
                m.effective_strength = new_strength
                updated += 1
            if not m.is_pinned and m.memory_type != "preference" and new_strength < ARCHIVE_THRESHOLD:
                m.is_archived = True
                archived += 1
        db.commit()
        offset += batch_size
    logger.info(f"[memory] decay pass updated={updated} archived={archived}")
    return {"updated": updated, "archived": archived}


# ==================== 周期摘要 ====================

def build_weekly_digest(
    db: Session, *, pet_avatar_id: int, user_id: int, llm_summarize=None
) -> Optional[MemoryDigest]:
    """
    把过去 7 天的 episodic 记忆蒸馏为一条 semantic 摘要。

    llm_summarize: 可选回调 (memories: List[PetMemory]) -> dict
        预期返回 {"summary": str, "key_themes": [..], "dominant_emotion": str}
        不传则用规则版兜底。
    """
    end = _now()
    start = end - timedelta(days=7)
    mems = (
        db.query(PetMemory)
        .filter(
            PetMemory.pet_avatar_id == pet_avatar_id,
            PetMemory.user_id == user_id,
            PetMemory.memory_type == "episodic",
            PetMemory.created_at >= start,
            PetMemory.is_archived.is_(False),
        )
        .order_by(desc(PetMemory.importance), desc(PetMemory.created_at))
        .limit(50)
        .all()
    )
    if len(mems) < 3:
        return None

    if llm_summarize:
        try:
            payload = llm_summarize(mems)
        except Exception as e:
            logger.warning(f"[memory] llm_summarize failed, fallback: {e}")
            payload = _rule_based_digest(mems)
    else:
        payload = _rule_based_digest(mems)

    digest = MemoryDigest(
        pet_avatar_id=pet_avatar_id,
        user_id=user_id,
        period_type="weekly",
        period_start=start,
        period_end=end,
        summary=payload["summary"],
        key_themes=payload.get("key_themes"),
        dominant_emotion=payload.get("dominant_emotion"),
        sourced_memory_ids=[m.id for m in mems],
    )
    db.add(digest)

    # 同时把摘要本身写为一条 semantic 记忆
    write_memory(
        db,
        pet_avatar_id=pet_avatar_id,
        user_id=user_id,
        content=payload["summary"],
        memory_type="semantic",
        importance=7,
        emotion=payload.get("dominant_emotion"),
        source="weekly_digest",
        summary=payload["summary"][:120],
    )
    db.flush()
    return digest


def _rule_based_digest(mems: List[PetMemory]) -> Dict[str, Any]:
    """无 LLM 时的兜底摘要：基于情绪频次和高重要度记忆拼接。"""
    emo_counter: Dict[str, int] = {}
    for m in mems:
        if m.emotion:
            emo_counter[m.emotion] = emo_counter.get(m.emotion, 0) + 1
    dominant = max(emo_counter, key=emo_counter.get) if emo_counter else "neutral"

    top = sorted(mems, key=lambda x: x.importance or 0, reverse=True)[:3]
    summary_lines = [f"过去一周，主人主导情绪偏向 {dominant}。重要片段："]
    for m in top:
        summary_lines.append(f"- {m.summary or m.content[:80]}")

    themes = []
    for kw in ("加班", "失眠", "聚会", "出差", "运动", "旅行", "生病"):
        if any(kw in (m.content or "") for m in mems):
            themes.append(kw)

    return {
        "summary": "\n".join(summary_lines),
        "key_themes": themes,
        "dominant_emotion": dominant,
    }


# ==================== 统计 ====================

def garden_stats(db: Session, *, pet_avatar_id: int, user_id: int) -> Dict[str, Any]:
    """记忆花园 UI 用：整体统计。"""
    base = db.query(PetMemory).filter(
        PetMemory.pet_avatar_id == pet_avatar_id,
        PetMemory.user_id == user_id,
    )
    total = base.count()
    by_type = dict(
        base.with_entities(PetMemory.memory_type, func.count())
        .group_by(PetMemory.memory_type)
        .all()
    )
    by_emotion = dict(
        base.with_entities(PetMemory.emotion, func.count())
        .filter(PetMemory.emotion.isnot(None))
        .group_by(PetMemory.emotion)
        .all()
    )
    pinned = base.filter(PetMemory.is_pinned.is_(True)).count()
    archived = base.filter(PetMemory.is_archived.is_(True)).count()
    oldest = base.with_entities(func.min(PetMemory.created_at)).scalar()
    newest = base.with_entities(func.max(PetMemory.created_at)).scalar()

    return {
        "total": total,
        "by_type": by_type,
        "by_emotion": by_emotion,
        "pinned_count": pinned,
        "archived_count": archived,
        "oldest_memory_at": oldest,
        "newest_memory_at": newest,
        "top_themes": [],
    }
