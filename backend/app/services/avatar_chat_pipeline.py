"""
PetPal - 分身对话增强管线

为 pet_avatar_service.chat_as_pet() 提供：
- prelude(): 对话前注入记忆 + 主人画像，组装为 system prompt 增量片段
- post_hook(): 对话后写入记忆 / 记录信号 / 广播 ASP 事件给所有终端

设计原则：
- 不破坏原有 chat_with_pet 的核心流程，纯增量调用
- 任意子模块异常都不能阻塞主对话流（全部 try/except）
"""
from typing import Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.avatar import PetAvatar
from app.services import memory_service, owner_profile_service
from app.services.avatar_render import (
    AvatarStateEvent, SpeechPayload, get_orchestrator,
)


# ==================== 对话前 prelude ====================

def build_chat_prelude(
    db: Session, *, avatar: PetAvatar, user: User, query: str
) -> str:
    """
    返回一段额外的 system prompt 片段，包含：
    - 检索出的 top-K 记忆
    - 主人画像（如果可见且置信度足够）

    无任何可注入内容时返回空串。
    """
    blocks = []

    # 1. 长期记忆（最多 5 条）
    try:
        mems = memory_service.retrieve_memories(
            db,
            pet_avatar_id=avatar.id,
            user_id=user.id,
            query=query,
            top_k=5,
        )
        if mems:
            blocks.append(memory_service.format_memories_for_prompt(mems))
    except Exception as e:
        logger.warning(f"[chat_pipeline] retrieve_memories failed: {e}")

    # 2. 主人画像
    try:
        profile = owner_profile_service.load_profile_for_avatar(db, user_id=user.id)
        if profile:
            blocks.append(owner_profile_service.format_profile_for_prompt(profile))
    except Exception as e:
        logger.warning(f"[chat_pipeline] load_profile failed: {e}")

    if not blocks:
        return ""
    return "\n\n--- 你对主人的长期了解 ---\n" + "\n\n".join(blocks)


# ==================== 对话后 post hook ====================

async def post_chat_hook(
    db: Session,
    *,
    avatar: PetAvatar,
    user: User,
    user_message: str,
    assistant_message: str,
    chat_id: int,
    message_id: Optional[int] = None,
    detected_emotion: Optional[str] = None,
) -> None:
    """
    对话完成后异步执行的副作用：
    1. 抽取并写入新记忆
    2. 记录主人信号（消息行为 + 情感）
    3. 广播 ASP 事件给所有已绑定设备
    """
    # 1. 抽取记忆（优先用 LLM，失败自动降级到规则版）
    try:
        mem_data = await memory_service.extract_memory_from_message_llm(
            user_message=user_message, assistant_message=assistant_message,
        )
        if mem_data:
            memory_service.write_memory(
                db,
                pet_avatar_id=avatar.id,
                user_id=user.id,
                content=mem_data["content"],
                memory_type=mem_data["memory_type"],
                summary=mem_data.get("summary"),
                importance=mem_data["importance"],
                emotion=mem_data.get("emotion"),
                emotion_intensity=mem_data.get("emotion_intensity"),
                source="conversation",
                source_ref=f"chat:{chat_id}:msg:{message_id or ''}",
            )
    except Exception as e:
        logger.warning(f"[chat_pipeline] write_memory failed: {e}")

    # 2. 记录画像信号
    try:
        sentiment = owner_profile_service.analyze_message_sentiment(user_message)
        owner_profile_service.record_signal(
            db,
            user_id=user.id,
            signal_type="message",
            payload={"length": len(user_message), "chat_id": chat_id},
            sentiment_score=sentiment["score"],
            sentiment_label=sentiment["label"],
            text_excerpt=user_message[:200],
        )
    except Exception as e:
        logger.warning(f"[chat_pipeline] record_signal failed: {e}")

    # 提交以上两步（在调用方 commit 之外的副作用，独立提交以免影响主流程已 commit 的部分）
    try:
        db.commit()
    except Exception as e:
        logger.warning(f"[chat_pipeline] commit side-effects failed: {e}")
        db.rollback()

    # 3. 广播 ASP 事件
    try:
        emotion = detected_emotion or _infer_emotion_from_style(avatar.speaking_style)
        event = AvatarStateEvent(
            avatar_id=avatar.id,
            user_id=user.id,
            type="speech",
            emotion=emotion,
            intensity=0.6,
            speech=SpeechPayload(
                text=assistant_message,
                voice_style=avatar.speaking_style,
            ),
        )
        await get_orchestrator().broadcast(db, event)
    except Exception as e:
        logger.warning(f"[chat_pipeline] broadcast failed: {e}")


# ==================== 辅助 ====================

_STYLE_TO_EMOTION = {
    "cute": "happy",
    "sassy": "proud",
    "lazy": "sleepy",
    "energetic": "happy",
    "gentle": "loving",
}


def _infer_emotion_from_style(style: Optional[str]) -> str:
    return _STYLE_TO_EMOTION.get(style or "cute", "neutral")
