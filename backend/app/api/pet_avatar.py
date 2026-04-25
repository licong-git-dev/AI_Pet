"""
PetPal - 宠物数字分身API

提供数字分身创建与管理、AI宠物对话、表情包生成、性格分析等功能。
"""
import json
import httpx
import ipaddress
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet, PetBreed
from app.models.avatar import PetAvatar, PetAvatarChat, PetAvatarMessage, PetSticker, PersonalityProfile
from app.schemas.pet_avatar import (
    CreateAvatarRequest, UpdateAvatarRequest, AvatarChatRequest,
    GenerateStickerRequest, GeneratePersonalityRequest,
)
from app.utils.deps import get_current_user
from app.utils.response import success, page_response
from app.config import settings as app_settings
from app.services import avatar_chat_pipeline
from app.services.pet_avatar_service import (
    analyze_pet_appearance,
    generate_personality_analysis,
    build_pet_chat_system_prompt,
    chat_as_pet,
    build_sticker_prompt,
    submit_sticker_generation,
    check_sticker_task_status,
    determine_persona_type,
    SPEAKING_STYLES,
    STICKER_EMOTIONS,
    PERSONA_TYPES,
)

router = APIRouter()


# ==================== 工具函数 ====================

def _verify_pet_ownership(db: Session, pet_id: int, user_id: int) -> Pet:
    """验证宠物归属"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == user_id,
        Pet.deleted_at.is_(None)
    ).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")
    return pet


def _get_pet_info_dict(pet: Pet) -> dict:
    """获取宠物信息字典"""
    personality = []
    if pet.personality:
        try:
            personality = json.loads(pet.personality) if isinstance(pet.personality, str) else pet.personality
        except (json.JSONDecodeError, TypeError):
            personality = []
    return {
        "name": pet.name,
        "pet_type": pet.pet_type,
        "breed_name": pet.breed_name,
        "weight": pet.weight,
        "health_status": getattr(pet, 'health_status', 'healthy'),
        "personality": personality,
        "age": getattr(pet, 'age', None),
        "age_months": getattr(pet, 'age_months', None),
        "avatar_url": getattr(pet, 'avatar_url', None),
    }


def _get_breed_info_dict(breed) -> dict:
    """获取品种信息字典（PetBreed 无 to_dict 方法）"""
    return {
        "name": breed.name,
        "pet_type": breed.pet_type,
        "character": breed.character or '',
        "care_tips": breed.care_tips or '',
        "common_diseases": breed.common_diseases or '',
        "diet_tips": breed.diet_tips or '',
        "description": breed.description or '',
    }


def _check_daily_limit(db: Session, model, user_id: int, limit: int, label: str):
    """检查用户每日使用次数是否超限"""
    if limit <= 0:
        return  # 0 表示不限制
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    count = db.query(func.count(model.id)).filter(
        model.user_id == user_id,
        model.created_at >= today_start
    ).scalar() or 0
    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"今日{label}次数已达上限（{limit}次/天），明天再来吧"
        )


# ==================== 静态路由 ====================

@router.get("/speaking-styles", summary="获取说话风格列表")
async def get_speaking_styles():
    """获取可用的说话风格列表（无需登录）"""
    styles = [
        {"key": k, "name": v["name"], "description": v["desc"]}
        for k, v in SPEAKING_STYLES.items()
    ]
    return success(data=styles)


@router.get("/sticker-emotions", summary="获取表情类型列表")
async def get_sticker_emotions():
    """获取可用的表情类型列表（无需登录）"""
    emotions = [
        {"key": k, "name": v["name"], "emoji": v["emoji"], "description": v["description"]}
        for k, v in STICKER_EMOTIONS.items()
    ]
    return success(data=emotions)


@router.get("/persona-types", summary="获取所有PetSona类型")
async def get_persona_types():
    """获取12种PetSona宠物性格类型列表（无需登录）"""
    types_list = [{"type_id": k, **v} for k, v in PERSONA_TYPES.items()]
    return success(data=types_list)


# ==================== 数字分身管理 ====================

@router.post("/create", summary="创建宠物数字分身")
async def create_avatar(
    request: CreateAvatarRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    为宠物创建数字分身。
    支持三种方式：
    1. 传 image_base64：AI 分析照片生成外貌描述和人设
    2. 传 photo_url 或宠物有头像：下载后 AI 分析
    3. 都不传：使用品种默认人设
    """
    # 验证说话风格
    if request.speaking_style not in SPEAKING_STYLES:
        raise HTTPException(status_code=400, detail="无效的说话风格")

    # 验证宠物归属
    pet = _verify_pet_ownership(db, request.pet_id, current_user.id)

    # 检查是否已有分身
    existing = db.query(PetAvatar).filter(PetAvatar.pet_id == request.pet_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该宠物已有数字分身，请直接使用或更新设置")

    pet_info = _get_pet_info_dict(pet)

    # 尝试 AI 分析外貌
    appearance_result = None
    if request.image_base64:
        try:
            appearance_result = await analyze_pet_appearance(request.image_base64, pet_info)
        except Exception as e:
            logger.warning(f"AI 外貌分析异常: {str(e)}")
    elif request.photo_url or getattr(pet, 'avatar_url', None):
        photo_url = request.photo_url or pet.avatar_url
        image_base64 = await _download_image_as_base64(photo_url)
        if image_base64:
            try:
                appearance_result = await analyze_pet_appearance(image_base64, pet_info)
            except Exception as e:
                logger.warning(f"AI 外貌分析异常: {str(e)}")

    # 如果 AI 分析失败或没有图片，使用默认结果
    if not appearance_result:
        appearance_result = {
            "appearance_desc": f"一只可爱的{pet.breed_name or pet.pet_type}",
            "suggested_traits": ["友善", "活泼", "好奇"],
            "suggested_style": request.speaking_style,
            "first_person_intro": f"嗨！我是{pet.name}，很高兴认识你！"
        }

    # 创建分身记录
    avatar = PetAvatar(
        pet_id=request.pet_id,
        user_id=current_user.id,
        appearance_desc=appearance_result.get("appearance_desc"),
        persona={
            "first_person_intro": appearance_result.get("first_person_intro"),
            "suggested_traits": appearance_result.get("suggested_traits"),
        },
        speaking_style=request.speaking_style,
    )
    db.add(avatar)
    db.commit()
    db.refresh(avatar)

    return success(data=avatar.to_dict(), message="数字分身创建成功")


@router.get("/{pet_id}", summary="获取宠物数字分身信息")
async def get_avatar(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取指定宠物的数字分身信息"""
    _verify_pet_ownership(db, pet_id, current_user.id)

    avatar = db.query(PetAvatar).filter(PetAvatar.pet_id == pet_id).first()
    if not avatar:
        return success(data=None, message="该宠物还没有数字分身")

    return success(data=avatar.to_dict())


@router.put("/{pet_id}", summary="更新数字分身设置")
async def update_avatar(
    pet_id: int,
    request: UpdateAvatarRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新数字分身的说话风格或人设"""
    _verify_pet_ownership(db, pet_id, current_user.id)

    avatar = db.query(PetAvatar).filter(
        PetAvatar.pet_id == pet_id,
        PetAvatar.user_id == current_user.id
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="数字分身不存在")

    if request.speaking_style:
        if request.speaking_style not in SPEAKING_STYLES:
            raise HTTPException(status_code=400, detail="无效的说话风格")
        avatar.speaking_style = request.speaking_style

    if request.persona:
        avatar.persona = request.persona

    db.commit()
    db.refresh(avatar)

    return success(data=avatar.to_dict(), message="更新成功")


# ==================== 宠物AI对话 ====================

@router.post("/{pet_id}/chat", summary="和宠物聊天")
async def chat_with_pet(
    pet_id: int,
    request: AvatarChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    和宠物数字分身聊天。
    宠物以第一人称回复，具有独特的说话风格和性格。
    """
    pet = _verify_pet_ownership(db, pet_id, current_user.id)

    # 获取分身
    avatar = db.query(PetAvatar).filter(PetAvatar.pet_id == pet_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="请先创建宠物数字分身")

    # 获取品种信息
    breed = None
    if pet.breed_id:
        breed = db.query(PetBreed).filter(PetBreed.id == pet.breed_id).first()

    # 获取或创建会话
    chat = None
    if request.chat_id:
        chat = db.query(PetAvatarChat).filter(
            PetAvatarChat.id == request.chat_id,
            PetAvatarChat.user_id == current_user.id
        ).first()
        if not chat:
            raise HTTPException(status_code=404, detail="会话不存在")

    if not chat:
        chat = PetAvatarChat(
            avatar_id=avatar.id,
            user_id=current_user.id,
            title=request.message[:50],
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # 获取历史消息：取最新 40 条（倒序取、再反转），确保上下文是真正的最近对话
    history_msgs = db.query(PetAvatarMessage).filter(
        PetAvatarMessage.chat_id == chat.id
    ).order_by(desc(PetAvatarMessage.created_at)).limit(40).all()
    history_msgs = list(reversed(history_msgs))

    messages = [
        {"role": m.role, "content": m.content}
        for m in history_msgs
        if m.role in ("user", "assistant")  # 过滤非法角色，防止 system prompt 注入
    ]

    # 构建 system prompt
    pet_info = _get_pet_info_dict(pet)
    breed_data = _get_breed_info_dict(breed) if breed else None
    system_prompt = build_pet_chat_system_prompt(avatar.to_dict(), pet_info, breed_data)

    # 注入长期记忆 + 主人画像（三大支柱集成点）
    try:
        prelude = avatar_chat_pipeline.build_chat_prelude(
            db, avatar=avatar, user=current_user, query=request.message,
        )
        if prelude:
            system_prompt = system_prompt + prelude
    except Exception as e:
        logger.warning(f"对话 prelude 失败（已忽略）: {e}")

    # 调用AI（异常时返回友好回复而非 500）
    try:
        ai_reply = await chat_as_pet(system_prompt, messages, request.message)
    except Exception as e:
        logger.error(f"宠物对话 AI 调用异常: {str(e)}")
        ai_reply = "*歪头看着你* 呜...我脑子有点转不过来了，你再跟我说一次好不好？"

    # 先保存用户消息（在AI调用后保存，避免 autoflush 导致历史消息重复）
    user_msg = PetAvatarMessage(
        chat_id=chat.id,
        role="user",
        content=request.message
    )
    db.add(user_msg)

    # 保存AI回复
    ai_msg = PetAvatarMessage(
        chat_id=chat.id,
        role="assistant",
        content=ai_reply
    )
    db.add(ai_msg)

    # 更新统计
    chat.message_count = (chat.message_count or 0) + 2
    avatar.chat_count = (avatar.chat_count or 0) + 1

    db.commit()

    # 三大支柱集成：写入新记忆 + 记录信号 + 广播 ASP 事件
    try:
        await avatar_chat_pipeline.post_chat_hook(
            db,
            avatar=avatar,
            user=current_user,
            user_message=request.message,
            assistant_message=ai_reply,
            chat_id=chat.id,
            message_id=ai_msg.id,
        )
    except Exception as e:
        logger.warning(f"对话 post_hook 失败（已忽略）: {e}")

    return success(data={
        "reply": ai_reply,
        "chat_id": chat.id,
        "message_id": ai_msg.id,
    })


@router.get("/{pet_id}/chats", summary="获取对话会话列表")
async def get_chat_list(
    pet_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取与该宠物的对话会话列表"""
    _verify_pet_ownership(db, pet_id, current_user.id)

    avatar = db.query(PetAvatar).filter(PetAvatar.pet_id == pet_id).first()
    if not avatar:
        return page_response(data=[], page=page, page_size=page_size, total=0)

    query = db.query(PetAvatarChat).filter(
        PetAvatarChat.avatar_id == avatar.id,
        PetAvatarChat.user_id == current_user.id
    ).order_by(desc(PetAvatarChat.updated_at))

    total = query.count()
    chats = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[c.to_dict() for c in chats],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/{pet_id}/chat/{chat_id}", summary="获取对话详情")
async def get_chat_detail(
    pet_id: int,
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取对话完整消息记录"""
    _verify_pet_ownership(db, pet_id, current_user.id)

    chat = db.query(PetAvatarChat).filter(
        PetAvatarChat.id == chat_id,
        PetAvatarChat.user_id == current_user.id
    ).first()
    if not chat:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = db.query(PetAvatarMessage).filter(
        PetAvatarMessage.chat_id == chat_id
    ).order_by(PetAvatarMessage.created_at).all()

    result = chat.to_dict()
    result["messages"] = [m.to_dict() for m in messages]

    return success(data=result)


# ==================== 表情包生成 ====================

@router.post("/{pet_id}/sticker", summary="生成宠物表情包")
async def generate_sticker(
    pet_id: int,
    request: GenerateStickerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    异步生成宠物表情包。
    提交后返回 sticker_id，前端轮询状态。
    """
    if request.emotion not in STICKER_EMOTIONS:
        raise HTTPException(status_code=400, detail="无效的表情类型")

    pet = _verify_pet_ownership(db, pet_id, current_user.id)

    # 每日生成次数限制
    _check_daily_limit(
        db, PetSticker, current_user.id,
        getattr(app_settings, 'sticker_daily_limit', 10), "表情包生成"
    )

    # 获取分身的外貌描述
    avatar = db.query(PetAvatar).filter(PetAvatar.pet_id == pet_id).first()
    appearance_desc = avatar.appearance_desc if avatar else ""

    # 确定照片URL
    photo_url = request.photo_url or pet.avatar_url
    if not photo_url:
        raise HTTPException(status_code=400, detail="请上传照片或为宠物设置头像")

    # 构建 prompt
    pet_info = _get_pet_info_dict(pet)
    prompt = build_sticker_prompt(pet_info, appearance_desc, request.emotion)

    # 提交生成任务
    try:
        task_id = await submit_sticker_generation(prompt)
    except Exception as e:
        logger.warning(f"表情包提交异常: {str(e)}")
        task_id = None

    # 创建记录
    sticker = PetSticker(
        pet_id=pet_id,
        user_id=current_user.id,
        source_photo_url=photo_url,
        emotion=request.emotion,
        prompt_used=prompt,
        task_id=task_id,
        status="generating" if task_id else "failed",
        error_message=None if task_id else "提交生成任务失败"
    )
    db.add(sticker)

    # 更新分身统计（仅成功提交时计数）
    if avatar and task_id:
        avatar.sticker_count = (avatar.sticker_count or 0) + 1

    db.commit()
    db.refresh(sticker)

    # 如果有task_id，触发Celery异步轮询任务
    if task_id:
        try:
            from app.tasks.avatar import process_sticker_generation
            process_sticker_generation.delay(sticker.id)
        except Exception as e:
            logger.warning(f"Celery 任务入队失败（sticker_id={sticker.id}）: {str(e)}")
            # 标记为失败，避免永远卡在 generating 状态
            sticker.status = "failed"
            sticker.error_message = "任务调度失败，请重试"
            db.commit()
            db.refresh(sticker)

    return success(data=sticker.to_dict(), message="表情包生成中，请稍候")


@router.get("/{pet_id}/sticker/{sticker_id}", summary="查询表情包状态")
async def get_sticker_status(
    pet_id: int,
    sticker_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """查询表情包生成状态"""
    sticker = db.query(PetSticker).filter(
        PetSticker.id == sticker_id,
        PetSticker.pet_id == pet_id,
        PetSticker.user_id == current_user.id
    ).first()
    if not sticker:
        raise HTTPException(status_code=404, detail="表情包不存在")

    # 如果仍在生成中且有task_id，实时查询状态
    if sticker.status == "generating" and sticker.task_id:
        result = await check_sticker_task_status(sticker.task_id)
        if result["status"] == "SUCCEEDED" and result["image_url"]:
            sticker.sticker_url = result["image_url"]
            sticker.status = "completed"
            db.commit()
            db.refresh(sticker)
        elif result["status"] == "FAILED":
            sticker.status = "failed"
            sticker.error_message = "生成失败"
            db.commit()
            db.refresh(sticker)

    return success(data=sticker.to_dict())


@router.get("/{pet_id}/stickers", summary="获取宠物表情包列表")
async def get_sticker_list(
    pet_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取该宠物的所有表情包"""
    _verify_pet_ownership(db, pet_id, current_user.id)

    query = db.query(PetSticker).filter(
        PetSticker.pet_id == pet_id,
        PetSticker.user_id == current_user.id,
        PetSticker.status == "completed"
    ).order_by(desc(PetSticker.created_at))

    total = query.count()
    stickers = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[s.to_dict() for s in stickers],
        page=page,
        page_size=page_size,
        total=total
    )


# ==================== 性格分析 ====================

@router.post("/{pet_id}/personality", summary="生成性格分析")
async def create_personality(
    pet_id: int,
    request: GeneratePersonalityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """为宠物生成AI性格分析档案"""
    pet = _verify_pet_ownership(db, pet_id, current_user.id)

    # 每日分析次数限制
    _check_daily_limit(
        db, PersonalityProfile, current_user.id,
        getattr(app_settings, 'personality_daily_limit', 5), "性格分析"
    )

    pet_info = _get_pet_info_dict(pet)

    # 获取品种信息
    breed_info = None
    if pet.breed_id:
        breed = db.query(PetBreed).filter(PetBreed.id == pet.breed_id).first()
        if breed:
            breed_info = _get_breed_info_dict(breed)

    # 调用AI分析（异常时使用默认结果）
    try:
        result = await generate_personality_analysis(
            image_base64=None,
            pet_info=pet_info,
            breed_info=breed_info
        )
    except Exception as e:
        logger.warning(f"AI 性格分析异常: {str(e)}")
        result = {
            "energy_level": 70, "affection_level": 80, "curiosity_level": 75,
            "foodie_level": 85, "intelligence_level": 70, "mischief_level": 60,
            "personality_tags": ["可爱", "友善", "好奇", "贪吃", "活泼"],
            "fun_description": f"{pet.name}是一个充满好奇心的小家伙！",
            "analysis_text": f"{pet.name}性格友善温和，喜欢与主人互动。",
            "spirit_animal": "小太阳", "motto": "吃饱了就是最大的幸福！"
        }

    # 计算 PetSona 类型
    persona_type_id = determine_persona_type(result)
    persona_info = PERSONA_TYPES.get(persona_type_id, PERSONA_TYPES["solar_explorer"])

    # 保存档案
    profile = PersonalityProfile(
        pet_id=pet_id,
        user_id=current_user.id,
        photo_url=request.photo_url or pet.avatar_url,
        energy_level=result.get("energy_level"),
        affection_level=result.get("affection_level"),
        curiosity_level=result.get("curiosity_level"),
        foodie_level=result.get("foodie_level"),
        intelligence_level=result.get("intelligence_level"),
        mischief_level=result.get("mischief_level"),
        analysis_text=result.get("analysis_text"),
        personality_tags=result.get("personality_tags"),
        fun_description=result.get("fun_description"),
        spirit_animal=result.get("spirit_animal"),
        motto=result.get("motto"),
        persona_type=persona_type_id,
        persona_type_name=persona_info["name"],
        persona_type_emoji=persona_info["emoji"],
        persona_type_color=persona_info["color"],
        persona_type_slogan=persona_info["slogan"],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return success(data=profile.to_dict(), message="性格分析完成")


@router.get("/{pet_id}/personality/history", summary="性格分析历史")
async def get_personality_history(
    pet_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物的性格分析历史（必须注册在 /{pet_id}/personality 之前，否则 FastAPI 会把 "history" 当作 pet_id 匹配）"""
    _verify_pet_ownership(db, pet_id, current_user.id)

    query = db.query(PersonalityProfile).filter(
        PersonalityProfile.pet_id == pet_id,
        PersonalityProfile.user_id == current_user.id
    ).order_by(desc(PersonalityProfile.created_at))

    total = query.count()
    profiles = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[p.to_dict() for p in profiles],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/{pet_id}/personality", summary="获取最新性格档案")
async def get_personality(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物最新的性格分析档案"""
    _verify_pet_ownership(db, pet_id, current_user.id)

    profile = db.query(PersonalityProfile).filter(
        PersonalityProfile.pet_id == pet_id,
        PersonalityProfile.user_id == current_user.id
    ).order_by(desc(PersonalityProfile.created_at)).first()

    if not profile:
        return success(data=None, message="还没有性格分析，快去生成一份吧")

    return success(data=profile.to_dict())


# ==================== 内部辅助函数 ====================

async def _download_image_as_base64(url: str) -> Optional[str]:
    """从 URL 下载图片并转为 base64 字符串（含 SSRF 防护）"""
    import base64

    # SSRF 防护：异步校验 URL 合法性（避免同步 DNS 阻塞事件循环）
    if not await _is_safe_url_async(url):
        logger.warning(f"拒绝不安全的 URL: {url}")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
            response = await client.get(url)

            # 跟随重定向前检查目标 URL
            if response.is_redirect:
                redirect_url = str(response.headers.get('location', ''))
                if not redirect_url or not await _is_safe_url_async(redirect_url):
                    logger.warning(f"拒绝重定向到不安全的 URL: {redirect_url!r}")
                    return None
                response = await client.get(redirect_url)

            if response.status_code == 200:
                # 限制下载大小：最大 10MB
                if len(response.content) > 10 * 1024 * 1024:
                    logger.warning(f"图片过大: {len(response.content)} bytes")
                    return None
                content_type = response.headers.get('content-type', 'image/jpeg')
                if 'image' in content_type:
                    return base64.b64encode(response.content).decode('utf-8')
    except Exception as e:
        logger.warning(f"下载图片失败: {url}, error: {str(e)}")
    return None


def _is_safe_url(url: str) -> bool:
    """检查 URL 是否安全（防止 SSRF 攻击）。
    注意：DNS 解析部分为同步调用，调用方应通过 `_is_safe_url_async` 包装后在线程池中执行，避免阻塞事件循环。
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # 只允许 http/https 协议
    if parsed.scheme not in ('http', 'https'):
        return False

    # 必须有主机名
    hostname = parsed.hostname
    if not hostname:
        return False

    # 禁止访问内网地址
    try:
        import socket
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
        # 禁止私有 IP、环回地址、链路本地地址
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except (socket.gaierror, ValueError):
        # DNS 解析失败则拒绝
        return False

    return True


async def _is_safe_url_async(url: str) -> bool:
    """`_is_safe_url` 的异步包装，将同步 DNS 解析卸载到线程池，
    避免在 FastAPI 异步事件循环中阻塞。"""
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _is_safe_url, url)
