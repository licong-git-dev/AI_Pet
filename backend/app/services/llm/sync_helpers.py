"""
PetPal - LLM 同步包装器

Celery 任务是同步的，但 LLM 客户端是 async 的。
本模块提供 asyncio.run 包装好的同步函数，供 task 调用。
"""
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.llm import get_llm, prompts


def _run_async(coro):
    """跨版本兼容地跑一个 coroutine 到结束。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 罕见：在已有事件循环中调用，回退到新循环
            return asyncio.new_event_loop().run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


def summarize_memories_sync(memory_objs) -> Optional[Dict[str, Any]]:
    """
    供 memory_service.build_weekly_digest 用的 LLM 回调。
    输入是 PetMemory ORM 对象列表，输出 {summary, key_themes, dominant_emotion}。
    任何异常返回 None，调用方会自行兜底。
    """
    llm = get_llm()
    if not getattr(llm, "is_available", False):
        return None
    payload_list = [
        {
            "content": getattr(m, "content", ""),
            "importance": getattr(m, "importance", 5),
            "emotion": getattr(m, "emotion", None),
            "happened_at": getattr(m, "happened_at", None).isoformat() if getattr(m, "happened_at", None) else None,
            "created_at": getattr(m, "created_at", None).isoformat() if getattr(m, "created_at", None) else None,
        }
        for m in memory_objs
    ]
    msgs = prompts.weekly_digest_messages(payload_list)
    try:
        return _run_async(llm.complete_json(msgs, temperature=0.5))
    except Exception as e:
        logger.warning(f"[llm.sync_helpers] weekly digest failed: {e}")
        return None


def wrapped_compose_sync(*, raw_stats, top_memories, profile=None) -> Optional[Dict[str, Any]]:
    """
    供 wrapped_service.build_wrapped 用的 LLM 回调。
    输入是已经聚合好的统计 dict + top_memories 列表，输出 {intro, secrets, closing}。
    """
    llm = get_llm()
    if not getattr(llm, "is_available", False):
        return None
    pet_name = "你的分身"
    if profile:
        try:
            pa = profile.pet_attachment or {}
            nicknames = pa.get("nicknames") or []
            if nicknames:
                pet_name = nicknames[0]
        except Exception:
            pass
    msgs = prompts.wrapped_compose_messages(raw_stats, top_memories, pet_name=pet_name)
    try:
        return _run_async(llm.complete_json(msgs, temperature=0.7, max_tokens=2048))
    except Exception as e:
        logger.warning(f"[llm.sync_helpers] wrapped compose failed: {e}")
        return None


def build_profile_sync(signal_objs) -> Optional[Dict[str, Any]]:
    """
    供 owner_profile_service.build_profile 用的 LLM 回调。
    输入 OwnerSignal 列表，输出 {daily_rhythm, emotional_baseline, ...}。
    """
    llm = get_llm()
    if not getattr(llm, "is_available", False):
        return None
    payload_list = [
        {
            "signal_type": getattr(s, "signal_type", None),
            "recorded_at": getattr(s, "recorded_at", None).isoformat() if getattr(s, "recorded_at", None) else None,
            "sentiment_label": getattr(s, "sentiment_label", None),
            "text_excerpt": getattr(s, "text_excerpt", None),
            "payload": getattr(s, "payload", None) or {},
        }
        for s in signal_objs
    ]
    msgs = prompts.build_profile_messages(payload_list)
    try:
        return _run_async(llm.complete_json(msgs, temperature=0.3))
    except Exception as e:
        logger.warning(f"[llm.sync_helpers] build profile failed: {e}")
        return None
