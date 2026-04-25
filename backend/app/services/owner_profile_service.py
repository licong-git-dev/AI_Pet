"""
PetPal - 主人画像服务

- record_signal(): 写入一条原子信号
- analyze_message_sentiment(): 规则版情感分析（无 LLM 时兜底）
- build_profile(): 把过去 N 天的信号蒸馏成画像（可注入 llm_summarize）
- load_profile_for_avatar(): 给分身对话注入画像上下文
- pause_learning() / resume_learning()

参考：docs/PRODUCT_DESIGN.md §2
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from loguru import logger
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models.owner_profile import OwnerProfile, OwnerSignal


# ==================== 工具 ====================

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ==================== 信号采集 ====================

def record_signal(
    db: Session,
    *,
    user_id: int,
    signal_type: str,
    payload: Optional[Dict[str, Any]] = None,
    sentiment_score: Optional[float] = None,
    sentiment_label: Optional[str] = None,
    text_excerpt: Optional[str] = None,
) -> OwnerSignal:
    """写入一条信号。所有写入路径的唯一入口，便于后续加采样/限流。"""
    # 暂停学习时不写信号
    profile = db.query(OwnerProfile).filter(OwnerProfile.user_id == user_id).first()
    if profile and profile.is_learning_paused:
        if not profile.pause_until or profile.pause_until > _now():
            logger.debug(f"[profile] signal skipped (paused) user={user_id}")
            return None

    sig = OwnerSignal(
        user_id=user_id,
        signal_type=signal_type,
        payload=payload,
        sentiment_score=sentiment_score,
        sentiment_label=sentiment_label,
        text_excerpt=(text_excerpt or "")[:255] or None,
    )
    db.add(sig)
    db.flush()
    return sig


# ==================== 情感分析（规则兜底） ====================

_POS_WORDS = ("开心", "高兴", "棒", "爱", "喜欢", "满足", "幸福", "舒服")
_NEG_WORDS = ("难过", "伤心", "累", "崩溃", "压力", "焦虑", "烦", "孤独", "失眠", "哭")
_ANGER_WORDS = ("气死", "讨厌", "恶心", "可恶", "fuck", "操")


def analyze_message_sentiment(text: str) -> Dict[str, Any]:
    """规则版情感分析。返回 {score: -1~1, label: str}。"""
    if not text:
        return {"score": 0.0, "label": "neutral"}
    t = text.lower()
    pos = sum(1 for w in _POS_WORDS if w in t)
    neg = sum(1 for w in _NEG_WORDS if w in t)
    ang = sum(1 for w in _ANGER_WORDS if w in t)
    if ang >= 1:
        return {"score": -0.8, "label": "angry"}
    if neg > pos and neg >= 1:
        return {"score": min(-0.3, -0.2 * neg), "label": "sad"}
    if pos > neg and pos >= 1:
        return {"score": min(0.9, 0.3 * pos), "label": "happy"}
    return {"score": 0.0, "label": "neutral"}


# ==================== 画像构建 ====================

def build_profile(
    db: Session,
    *,
    user_id: int,
    window_days: int = 30,
    llm_summarize=None,
) -> OwnerProfile:
    """
    从过去 window_days 的信号重建画像。

    llm_summarize: 可选回调，输入 List[OwnerSignal] -> dict
        预期返回各维度 dict。不传则用规则版兜底。
    """
    end = _now()
    start = end - timedelta(days=window_days)
    signals: List[OwnerSignal] = (
        db.query(OwnerSignal)
        .filter(OwnerSignal.user_id == user_id, OwnerSignal.recorded_at >= start)
        .order_by(desc(OwnerSignal.recorded_at))
        .limit(5000)
        .all()
    )

    if llm_summarize:
        try:
            payload = llm_summarize(signals)
        except Exception as e:
            logger.warning(f"[profile] llm_summarize failed, fallback: {e}")
            payload = _rule_based_build(signals)
    else:
        payload = _rule_based_build(signals)

    profile = db.query(OwnerProfile).filter(OwnerProfile.user_id == user_id).first()
    if not profile:
        profile = OwnerProfile(user_id=user_id)
        db.add(profile)

    # 主人手动修正过的字段（is_user_locked 标记）目前未实现，预留位
    profile.daily_rhythm = payload.get("daily_rhythm") or profile.daily_rhythm
    profile.emotional_baseline = payload.get("emotional_baseline") or profile.emotional_baseline
    profile.relationships = payload.get("relationships") or profile.relationships
    profile.communication = payload.get("communication") or profile.communication
    profile.pet_attachment = payload.get("pet_attachment") or profile.pet_attachment

    profile.signal_count = len(signals)
    profile.confidence_score = _calc_confidence(signals)
    profile.last_built_at = _now()

    db.flush()
    logger.info(f"[profile] built user={user_id} signals={len(signals)} conf={profile.confidence_score:.2f}")
    return profile


def _rule_based_build(signals: List[OwnerSignal]) -> Dict[str, Any]:
    """规则版画像构建。不依赖 LLM，覆盖最关键的"节律 + 情感基线"两个维度。"""
    if not signals:
        return {}

    # 节律：从 login + chat_start 信号的 hour 分布推断
    activity_hours = []
    for s in signals:
        if s.signal_type in ("login", "chat_start", "message") and s.recorded_at:
            activity_hours.append(s.recorded_at.hour)
    daily_rhythm = {}
    if activity_hours:
        c = Counter(activity_hours)
        peak = [h for h, _ in c.most_common(3)]
        daily_rhythm = {
            "peak_active_hours": sorted(peak),
            "earliest_seen_hour": min(activity_hours),
            "latest_seen_hour": max(activity_hours),
        }
        # 简单推断作息
        late = [h for h in activity_hours if h >= 23 or h < 3]
        if len(late) > len(activity_hours) * 0.15:
            daily_rhythm["sleep_time"] = "≥23:30"
        early = [h for h in activity_hours if 6 <= h <= 8]
        if len(early) > len(activity_hours) * 0.1:
            daily_rhythm["wake_time"] = "≈07:30"

    # 情感基线
    emotion_counter = Counter()
    for s in signals:
        if s.sentiment_label:
            emotion_counter[s.sentiment_label] += 1
    dominant = [k for k, _ in emotion_counter.most_common(3)] or ["neutral"]
    emotional_baseline = {"dominant_moods": dominant}

    # 沟通偏好：消息长度均值
    lengths = []
    for s in signals:
        if s.signal_type == "message" and s.payload and "length" in s.payload:
            lengths.append(s.payload["length"])
    communication = {}
    if lengths:
        avg = sum(lengths) / len(lengths)
        if avg < 15:
            communication["length"] = "short"
        elif avg < 60:
            communication["length"] = "medium"
        else:
            communication["length"] = "long"

    return {
        "daily_rhythm": daily_rhythm or None,
        "emotional_baseline": emotional_baseline,
        "communication": communication or None,
    }


def _calc_confidence(signals: List[OwnerSignal]) -> float:
    """置信度：信号量 + 多样性。简单线性版，min(1, n/200) * 多样性系数"""
    n = len(signals)
    if n == 0:
        return 0.0
    diversity = len({s.signal_type for s in signals}) / 8.0
    return round(min(1.0, n / 200.0) * (0.5 + 0.5 * diversity), 3)


# ==================== 给分身用的画像上下文 ====================

def load_profile_for_avatar(db: Session, *, user_id: int) -> Optional[OwnerProfile]:
    """给对话时注入画像；如果 is_visible_to_avatar=False 或低置信度则返回 None。"""
    p = db.query(OwnerProfile).filter(OwnerProfile.user_id == user_id).first()
    if not p:
        return None
    if not p.is_visible_to_avatar:
        return None
    if (p.confidence_score or 0.0) < 0.1:
        return None
    return p


def format_profile_for_prompt(profile: OwnerProfile) -> str:
    """格式化为分身 system prompt 的一段文本。"""
    if not profile:
        return ""
    parts = ["以下是你（分身）对主人的了解，自然地融入对话，不要直接念给主人听："]
    if profile.daily_rhythm:
        parts.append(f"作息: {profile.daily_rhythm}")
    if profile.emotional_baseline:
        parts.append(f"情绪基线: {profile.emotional_baseline}")
    if profile.relationships:
        parts.append(f"关系/角色: {profile.relationships}")
    if profile.communication:
        parts.append(f"沟通偏好: {profile.communication}")
    if profile.pet_attachment:
        parts.append(f"主人对宠物的依恋: {profile.pet_attachment}")
    parts.append(f"画像置信度: {profile.confidence_score:.2f}（低于 0.5 时请保守）")
    return "\n".join(parts)


# ==================== 学习暂停 ====================

def pause_learning(db: Session, *, user_id: int, days: int = 7) -> OwnerProfile:
    p = db.query(OwnerProfile).filter(OwnerProfile.user_id == user_id).first()
    if not p:
        p = OwnerProfile(user_id=user_id)
        db.add(p)
    p.is_learning_paused = True
    p.pause_until = _now() + timedelta(days=days)
    db.flush()
    return p


def resume_learning(db: Session, *, user_id: int) -> OwnerProfile:
    p = db.query(OwnerProfile).filter(OwnerProfile.user_id == user_id).first()
    if not p:
        p = OwnerProfile(user_id=user_id)
        db.add(p)
    p.is_learning_paused = False
    p.pause_until = None
    db.flush()
    return p


def apply_user_overrides(db: Session, *, user_id: int, overrides: Dict[str, Any]) -> OwnerProfile:
    """主人手动修正画像。仅覆盖传入的字段。"""
    p = db.query(OwnerProfile).filter(OwnerProfile.user_id == user_id).first()
    if not p:
        p = OwnerProfile(user_id=user_id)
        db.add(p)
    field_map = {
        "daily_rhythm": "daily_rhythm",
        "emotional_baseline": "emotional_baseline",
        "relationships": "relationships",
        "communication": "communication",
        "pet_attachment": "pet_attachment",
        "is_visible_to_avatar": "is_visible_to_avatar",
    }
    for key, attr in field_map.items():
        if key in overrides and overrides[key] is not None:
            setattr(p, attr, overrides[key])
    db.flush()
    return p
