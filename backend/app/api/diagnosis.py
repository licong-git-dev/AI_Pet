"""
PetPal - AI健康诊断API
基于通义千问VL的图像诊断 + 多轮问诊对话
"""
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.diagnosis import HealthDiagnosis, DiagnosisConversation
from app.schemas.diagnosis import (
    DiagnoseRequest, DiagnoseResponse,
    DiagnosisChatRequest, DiagnosisChatResponse
)
from app.utils.deps import get_current_user
from app.utils.response import success, page_response
from app.services.qwen_vl_service import (
    build_diagnosis_prompt,
    build_chat_prompt,
    analyze_image_with_qwen_vl,
    analyze_symptom_only,
    chat_with_qwen,
    DIAGNOSIS_TYPE_CONFIG
)

router = APIRouter()


# ============ 静态路由（必须放在动态路由之前） ============

@router.get("/types", summary="获取诊断类型列表")
async def get_diagnosis_types():
    """获取支持的诊断类型列表（无需登录）"""
    types = []
    for type_id, config in DIAGNOSIS_TYPE_CONFIG.items():
        types.append({
            "id": type_id,
            "name": config["name"],
            "description": config["description"],
            "requires_image": type_id != "symptom"
        })

    return success(data=types)


@router.get("/history", summary="获取诊断历史")
async def get_diagnosis_history(
    pet_id: int = Query(None, description="宠物ID筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的诊断历史列表"""
    query = db.query(HealthDiagnosis).filter(
        HealthDiagnosis.user_id == current_user.id
    )

    if pet_id:
        query = query.filter(HealthDiagnosis.pet_id == pet_id)

    query = query.order_by(desc(HealthDiagnosis.created_at))

    total = query.count()
    diagnoses = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取宠物信息
    pet_ids = list(set([d.pet_id for d in diagnoses]))
    pets = db.query(Pet).filter(Pet.id.in_(pet_ids)).all() if pet_ids else []
    pet_map = {p.id: p for p in pets}

    items = []
    for d in diagnoses:
        item = d.to_dict()
        pet = pet_map.get(d.pet_id)
        item["pet_name"] = pet.name if pet else None
        items.append(item)

    return page_response(
        data=items,
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/last", summary="获取最近一次诊断")
async def get_last_diagnosis(
    pet_id: int = Query(None, description="宠物ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户最近一次诊断记录"""
    query = db.query(HealthDiagnosis).filter(
        HealthDiagnosis.user_id == current_user.id,
        HealthDiagnosis.status == "completed"
    )

    if pet_id:
        query = query.filter(HealthDiagnosis.pet_id == pet_id)

    diagnosis = query.order_by(desc(HealthDiagnosis.created_at)).first()

    if not diagnosis:
        return success(data=None)

    # 获取宠物信息
    pet = db.query(Pet).filter(Pet.id == diagnosis.pet_id).first()

    result = diagnosis.to_dict()
    result["pet_name"] = pet.name if pet else None

    return success(data=result)


@router.post("/", summary="AI健康诊断")
async def create_diagnosis(
    request: DiagnoseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建AI健康诊断

    - 支持图片诊断（皮肤、眼睛、口腔、粪便）
    - 支持纯症状描述诊断
    - 返回健康评分、风险等级、AI分析结果和建议
    """
    # 验证诊断类型
    if request.diagnosis_type not in DIAGNOSIS_TYPE_CONFIG:
        raise HTTPException(status_code=400, detail="无效的诊断类型")

    # 验证宠物归属
    pet = db.query(Pet).filter(
        Pet.id == request.pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    # 验证输入
    if request.diagnosis_type != "symptom" and not request.image_base64:
        raise HTTPException(status_code=400, detail="该诊断类型需要上传图片")

    if request.diagnosis_type == "symptom" and not request.symptom_desc:
        raise HTTPException(status_code=400, detail="请描述宠物症状")

    # 创建诊断记录（状态为processing）
    diagnosis = HealthDiagnosis(
        user_id=current_user.id,
        pet_id=request.pet_id,
        diagnosis_type=request.diagnosis_type,
        symptom_desc=request.symptom_desc,
        status="processing"
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)

    try:
        # 调用AI分析
        if request.diagnosis_type == "symptom":
            # 纯症状描述分析
            result = await analyze_symptom_only(
                pet_name=pet.name,
                pet_type=pet.pet_type,
                breed=pet.breed_name,
                age=str(pet.age) if pet.age else None,
                symptom_desc=request.symptom_desc
            )
        else:
            # 图片分析
            prompt = build_diagnosis_prompt(
                diagnosis_type=request.diagnosis_type,
                pet_name=pet.name,
                pet_type=pet.pet_type,
                breed=pet.breed_name,
                age=str(pet.age) if pet.age else None,
                weight=pet.weight,
                symptom_desc=request.symptom_desc
            )
            result = await analyze_image_with_qwen_vl(
                image_base64=request.image_base64,
                prompt=prompt
            )

        # 更新诊断记录
        diagnosis.health_score = result.get("health_score", 70)
        diagnosis.risk_level = result.get("risk_level", "medium")
        diagnosis.ai_analysis = result
        diagnosis.suggestions = {
            "items": result.get("suggestions", []),
            "urgency": result.get("urgency", "建议咨询兽医")
        }
        diagnosis.confidence = result.get("issues", [{}])[0].get("confidence", 0.5) if result.get("issues") else 0.5
        diagnosis.status = "completed"

        db.commit()
        db.refresh(diagnosis)

        return success(data={
            "diagnosis_id": diagnosis.id,
            "health_score": diagnosis.health_score,
            "risk_level": diagnosis.risk_level,
            "ai_analysis": diagnosis.ai_analysis,
            "suggestions": diagnosis.suggestions
        })

    except Exception as e:
        # 更新状态为失败
        diagnosis.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


# ============ 动态路由（必须放在静态路由之后） ============

@router.get("/{diagnosis_id}", summary="获取诊断详情")
async def get_diagnosis_detail(
    diagnosis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取诊断详情及对话历史"""
    diagnosis = db.query(HealthDiagnosis).filter(
        HealthDiagnosis.id == diagnosis_id,
        HealthDiagnosis.user_id == current_user.id
    ).first()

    if not diagnosis:
        raise HTTPException(status_code=404, detail="诊断记录不存在")

    # 获取对话历史
    conversations = db.query(DiagnosisConversation).filter(
        DiagnosisConversation.diagnosis_id == diagnosis_id
    ).order_by(DiagnosisConversation.created_at).all()

    # 获取宠物信息
    pet = db.query(Pet).filter(Pet.id == diagnosis.pet_id).first()

    result = diagnosis.to_dict()
    result["conversations"] = [c.to_dict() for c in conversations]
    result["pet_name"] = pet.name if pet else None
    result["pet_type"] = pet.pet_type if pet else None

    return success(data=result)


@router.post("/{diagnosis_id}/chat", summary="继续问诊对话")
async def chat_with_diagnosis(
    diagnosis_id: int,
    request: DiagnosisChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    在诊断结果基础上继续问诊对话

    - AI会基于诊断结果上下文回答问题
    - 支持多轮对话
    """
    # 验证诊断记录
    diagnosis = db.query(HealthDiagnosis).filter(
        HealthDiagnosis.id == diagnosis_id,
        HealthDiagnosis.user_id == current_user.id
    ).first()

    if not diagnosis:
        raise HTTPException(status_code=404, detail="诊断记录不存在")

    # 获取宠物信息
    pet = db.query(Pet).filter(Pet.id == diagnosis.pet_id).first()

    # 保存用户消息
    user_msg = DiagnosisConversation(
        diagnosis_id=diagnosis_id,
        role="user",
        content=request.message
    )
    db.add(user_msg)

    # 获取历史对话
    history = db.query(DiagnosisConversation).filter(
        DiagnosisConversation.diagnosis_id == diagnosis_id
    ).order_by(DiagnosisConversation.created_at).all()

    # 构建上下文
    diagnosis_context = {
        "diagnosis_type": diagnosis.diagnosis_type,
        "health_score": diagnosis.health_score,
        "risk_level": diagnosis.risk_level,
        "ai_analysis": diagnosis.ai_analysis
    }

    pet_info = {
        "name": pet.name if pet else "未知",
        "pet_type": pet.pet_type if pet else "未知",
        "breed": pet.breed_name if pet else None
    }

    system_prompt = build_chat_prompt(diagnosis_context, pet_info)

    # 调用AI对话
    messages = [{"role": c.role, "content": c.content} for c in history]
    ai_reply = await chat_with_qwen(
        system_prompt=system_prompt,
        messages=messages,
        user_message=request.message
    )

    # 保存AI回复
    ai_msg = DiagnosisConversation(
        diagnosis_id=diagnosis_id,
        role="assistant",
        content=ai_reply
    )
    db.add(ai_msg)
    db.commit()

    return success(data={
        "reply": ai_reply,
        "conversation_id": ai_msg.id
    })
