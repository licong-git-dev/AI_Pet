"""
PetPal - 健康API (AI健康分析、智能问诊)
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.health import HealthRecord, HealthConsultation, ConsultationMessage
from app.schemas.health import (
    HealthAnalysisRequest, CreateHealthRecordRequest,
    ConsultationRequest, ConsultationMessageRequest
)
from app.utils.deps import get_current_user
from app.utils.response import success, page_response

router = APIRouter()


@router.post("/analyze", summary="AI健康分析")
async def analyze_health(
    request: HealthAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    AI分析宠物健康状况

    - 支持图片分析（皮肤、眼睛、便便等）
    - 支持症状描述分析
    - 返回可能的健康问题和建议
    """
    # 验证宠物归属
    pet = db.query(Pet).filter(
        Pet.id == request.pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    is_member_active = bool(
        current_user.member_level > 0
        and current_user.member_expire_at
        and current_user.member_expire_at > datetime.now()
    )
    points_cost = 12 if is_member_active else 20
    if current_user.points < points_cost:
        raise HTTPException(status_code=400, detail=f"积分不足，AI健康分析需要{points_cost}积分")

    # 调用AI服务进行健康分析
    from app.services.ai_health import analyze_pet_health
    analysis_result = await analyze_pet_health(
        pet_type=pet.pet_type,
        breed=pet.breed_name,
        age=pet.age,
        symptoms=request.description or "",
        image_urls=request.images,
        analysis_type=request.analysis_type
    )

    # 保存分析记录
    record = HealthRecord(
        pet_id=request.pet_id,
        user_id=current_user.id,
        record_type="ai_analysis",
        title="AI健康分析",
        description=request.description,
        ai_analysis=analysis_result.get("analysis"),
        ai_suggestions=analysis_result.get("suggestions"),
        image_urls=request.images,
        risk_level=analysis_result.get("risk_level", "low")
    )
    db.add(record)

    # 扣除积分
    from app.models.points import PointsRecord
    points_record = PointsRecord(
        user_id=current_user.id,
        points=-points_cost,
        balance=current_user.points - points_cost,
        source_type="health_analysis",
        description="AI健康分析消耗"
    )
    current_user.points -= points_cost
    db.add(points_record)

    db.commit()
    db.refresh(record)

    return success(data={
        "record_id": record.id,
        "analysis": analysis_result.get("analysis"),
        "suggestions": analysis_result.get("suggestions"),
        "risk_level": analysis_result.get("risk_level"),
        "possible_conditions": analysis_result.get("possible_conditions", []),
        "recommended_actions": analysis_result.get("recommended_actions", [])
    })


@router.post("/consultations", summary="创建问诊会话")
async def create_consultation(
    request: ConsultationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """创建AI智能问诊会话"""
    # 验证宠物归属
    pet = db.query(Pet).filter(
        Pet.id == request.pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    # 创建问诊会话
    consultation = HealthConsultation(
        pet_id=request.pet_id,
        user_id=current_user.id,
        chief_complaint=request.chief_complaint,
        symptoms=request.symptoms,
        duration=request.duration,
        images=request.image_urls,
        status="active"
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    # 生成AI初始回复
    from app.services.ai_health import generate_consultation_response
    ai_response = await generate_consultation_response(
        pet_type=pet.pet_type,
        breed=pet.breed_name,
        chief_complaint=request.chief_complaint,
        symptoms=request.symptoms,
        is_initial=True
    )

    # 保存AI消息
    ai_message = ConsultationMessage(
        consultation_id=consultation.id,
        role="assistant",
        content=ai_response
    )
    db.add(ai_message)
    db.commit()

    return success(data={
        "consultation_id": consultation.id,
        "initial_response": ai_response,
        "created_at": consultation.created_at.isoformat()
    }, message="问诊会话已创建")


@router.get("/consultations", summary="获取问诊历史")
async def get_consultations(
    pet_id: int = Query(None, description="宠物ID筛选"),
    status: str = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的问诊历史列表"""
    query = db.query(HealthConsultation).filter(
        HealthConsultation.user_id == current_user.id
    )

    if pet_id:
        query = query.filter(HealthConsultation.pet_id == pet_id)
    if status:
        query = query.filter(HealthConsultation.status == status)

    query = query.order_by(desc(HealthConsultation.created_at))

    total = query.count()
    consultations = query.offset((page - 1) * page_size).limit(page_size).all()
    pet_ids = [c.pet_id for c in consultations]
    pets = db.query(Pet).filter(Pet.id.in_(pet_ids)).all() if pet_ids else []
    pet_map = {pet.id: pet for pet in pets}

    return page_response(
        data=[c.to_dict(pet=pet_map.get(c.pet_id)) for c in consultations],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/consultations/{consultation_id}", summary="获取问诊详情")
async def get_consultation(
    consultation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取问诊会话详情及消息历史"""
    consultation = db.query(HealthConsultation).filter(
        HealthConsultation.id == consultation_id,
        HealthConsultation.user_id == current_user.id
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="问诊会话不存在")

    # 获取消息历史
    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.consultation_id == consultation_id
    ).order_by(ConsultationMessage.created_at).all()

    consultation_data = consultation.to_dict()
    consultation_data["messages"] = [m.to_dict() for m in messages]

    return success(data=consultation_data)


@router.post("/consultations/{consultation_id}/messages", summary="发送问诊消息")
async def send_consultation_message(
    consultation_id: int,
    request: ConsultationMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """在问诊会话中发送消息并获取AI回复"""
    consultation = db.query(HealthConsultation).filter(
        HealthConsultation.id == consultation_id,
        HealthConsultation.user_id == current_user.id,
        HealthConsultation.status == "active"
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="问诊会话不存在或已结束")

    # 保存用户消息
    user_message = ConsultationMessage(
        consultation_id=consultation_id,
        role="user",
        content=request.content,
        image_urls=request.image_urls
    )
    db.add(user_message)

    # 获取历史消息用于上下文
    history = db.query(ConsultationMessage).filter(
        ConsultationMessage.consultation_id == consultation_id
    ).order_by(ConsultationMessage.created_at).all()

    # 获取宠物信息
    pet = db.query(Pet).filter(Pet.id == consultation.pet_id).first()

    # 生成AI回复
    from app.services.ai_health import generate_consultation_response
    ai_response = await generate_consultation_response(
        pet_type=pet.pet_type if pet else "unknown",
        breed=pet.breed_name if pet else None,
        chief_complaint=consultation.chief_complaint,
        symptoms=consultation.symptoms,
        message_history=[{"role": m.role, "content": m.content} for m in history],
        new_message=request.content,
        image_urls=request.image_urls
    )

    # 保存AI回复
    ai_message = ConsultationMessage(
        consultation_id=consultation_id,
        role="assistant",
        content=ai_response
    )
    db.add(ai_message)
    db.commit()

    return success(data={
        "user_message_id": user_message.id,
        "ai_response": ai_response
    })


@router.post("/consultations/{consultation_id}/end", summary="结束问诊")
async def end_consultation(
    consultation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """结束问诊会话并生成总结"""
    consultation = db.query(HealthConsultation).filter(
        HealthConsultation.id == consultation_id,
        HealthConsultation.user_id == current_user.id,
        HealthConsultation.status == "active"
    ).first()

    if not consultation:
        raise HTTPException(status_code=404, detail="问诊会话不存在或已结束")

    # 获取所有消息
    messages = db.query(ConsultationMessage).filter(
        ConsultationMessage.consultation_id == consultation_id
    ).order_by(ConsultationMessage.created_at).all()

    # 生成问诊总结
    from app.services.ai_health import generate_consultation_summary
    summary = await generate_consultation_summary(
        chief_complaint=consultation.chief_complaint,
        messages=[{"role": m.role, "content": m.content} for m in messages]
    )

    # 更新问诊状态
    consultation.status = "completed"
    consultation.summary = summary.get("summary")
    consultation.diagnosis = summary.get("diagnosis")
    consultation.suggestions = summary.get("suggestions")
    consultation.ended_at = datetime.now()

    db.commit()

    return success(data={
        "summary": summary.get("summary"),
        "diagnosis": summary.get("diagnosis"),
        "suggestions": summary.get("suggestions")
    }, message="问诊已结束")


@router.get("/records", summary="获取健康记录")
async def get_health_records(
    pet_id: int = Query(..., description="宠物ID"),
    record_type: str = Query(None, description="记录类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物的健康记录列表"""
    # 验证宠物归属
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    query = db.query(HealthRecord).filter(HealthRecord.pet_id == pet_id)

    if record_type:
        query = query.filter(HealthRecord.record_type == record_type)

    query = query.order_by(desc(HealthRecord.created_at))

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[r.to_dict() for r in records],
        page=page,
        page_size=page_size,
        total=total
    )


@router.post("/records", summary="添加健康记录")
async def create_health_record(
    request: CreateHealthRecordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """手动添加健康记录（疫苗、驱虫、体检等）"""
    # 验证宠物归属
    pet = db.query(Pet).filter(
        Pet.id == request.pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    record = HealthRecord(
        pet_id=request.pet_id,
        record_type=request.record_type,
        title=request.title,
        description=request.description,
        record_date=request.record_date,
        next_date=request.next_date,
        hospital_name=request.hospital_name,
        doctor_name=request.doctor_name,
        cost=request.cost,
        image_urls=request.image_urls
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return success(data=record.to_dict(), message="记录添加成功")


@router.get("/records/{record_id}", summary="获取健康记录详情")
async def get_health_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取健康记录详情"""
    record = db.query(HealthRecord).filter(HealthRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 验证宠物归属
    pet = db.query(Pet).filter(
        Pet.id == record.pet_id,
        Pet.owner_id == current_user.id
    ).first()

    if not pet:
        raise HTTPException(status_code=403, detail="无权访问")

    return success(data=record.to_dict())


@router.delete("/records/{record_id}", summary="删除健康记录")
async def delete_health_record(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除健康记录"""
    record = db.query(HealthRecord).filter(HealthRecord.id == record_id).first()

    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    # 验证宠物归属
    pet = db.query(Pet).filter(
        Pet.id == record.pet_id,
        Pet.owner_id == current_user.id
    ).first()

    if not pet:
        raise HTTPException(status_code=403, detail="无权访问")

    db.delete(record)
    db.commit()

    return success(message="删除成功")
