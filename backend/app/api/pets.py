"""
PetPal - 宠物API

提供宠物档案管理、相册、疫苗记录、体重追踪等功能
"""
from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet, PetBreed, PetPhoto, VaccinationRecord, WeightRecord
from app.schemas.pet import (
    CreatePetRequest, UpdatePetRequest,
    AddPhotoRequest, AddVaccinationRequest, UpdateVaccinationRequest,
    AddWeightRequest
)
from app.utils.deps import get_current_user
from app.utils.response import success, page_response
from app.utils.xss_filter import sanitize_text
from app.utils.sql_guard import sanitize_search_query

router = APIRouter()


# ==================== 宠物基础CRUD ====================

@router.get("", summary="获取我的宠物列表")
async def get_my_pets(
    status: Optional[int] = Query(None, ge=1, le=3, description="状态筛选"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的所有宠物"""
    query = db.query(Pet).filter(
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    )

    if status:
        query = query.filter(Pet.status == status)

    pets = query.order_by(Pet.created_at.desc()).all()

    return success(data=[pet.to_dict(include_stats=True) for pet in pets])


@router.post("", summary="添加宠物")
async def create_pet(
    request: CreatePetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加新的宠物档案"""
    # 清理输入
    name = sanitize_text(request.name, max_length=100)
    personality = sanitize_text(request.personality) if request.personality else None

    pet = Pet(
        owner_id=current_user.id,
        name=name,
        pet_type=request.pet_type,
        breed_id=request.breed_id,
        breed_name=request.breed_name,
        avatar_url=request.avatar_url,
        gender=request.gender or 0,
        birthday=request.birthday,
        weight=request.weight,
        is_neutered=request.is_neutered or 0,
        personality=personality
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)

    return success(data=pet.to_dict(), message="添加成功")


@router.get("/{pet_id}", summary="获取宠物详情")
async def get_pet(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物详细信息"""
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.deleted_at.is_(None)).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    pet_data = pet.to_dict(include_stats=True)

    # 如果有品种ID,获取品种信息
    if pet.breed_id:
        breed = db.query(PetBreed).filter(PetBreed.id == pet.breed_id).first()
        if breed:
            pet_data["breed_info"] = {
                "id": breed.id,
                "name": breed.name,
                "description": breed.description,
                "care_tips": breed.care_tips,
                "common_diseases": breed.common_diseases
            }

    # 获取最近体重变化
    recent_weights = db.query(WeightRecord).filter(
        WeightRecord.pet_id == pet_id
    ).order_by(desc(WeightRecord.record_date)).limit(2).all()

    if len(recent_weights) >= 2:
        pet_data["weight_trend"] = {
            "current": recent_weights[0].weight,
            "previous": recent_weights[1].weight,
            "change": round(recent_weights[0].weight - recent_weights[1].weight, 2)
        }

    # 获取即将到期的疫苗
    upcoming_vaccines = db.query(VaccinationRecord).filter(
        VaccinationRecord.pet_id == pet_id,
        VaccinationRecord.next_date.isnot(None),
        VaccinationRecord.next_date >= date.today(),
        VaccinationRecord.next_date <= date.today() + timedelta(days=30)
    ).all()

    if upcoming_vaccines:
        pet_data["upcoming_vaccines"] = [v.to_dict() for v in upcoming_vaccines]

    return success(data=pet_data)


@router.put("/{pet_id}", summary="更新宠物信息")
async def update_pet(
    pet_id: int,
    request: UpdatePetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新宠物信息"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    update_data = request.model_dump(exclude_unset=True)

    # 清理文本输入
    if 'name' in update_data and update_data['name']:
        update_data['name'] = sanitize_text(update_data['name'], max_length=100)
    if 'personality' in update_data and update_data['personality']:
        update_data['personality'] = sanitize_text(update_data['personality'])

    for key, value in update_data.items():
        setattr(pet, key, value)

    # 如果更新了体重，同时添加体重记录
    if request.weight and request.weight != pet.weight:
        weight_record = WeightRecord(
            pet_id=pet_id,
            weight=request.weight,
            record_date=date.today()
        )
        db.add(weight_record)

    db.commit()
    db.refresh(pet)

    return success(data=pet.to_dict(), message="更新成功")


@router.delete("/{pet_id}", summary="删除宠物")
async def delete_pet(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除宠物档案（软删除）"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    pet.deleted_at = datetime.now()
    db.commit()

    return success(message="删除成功")


# ==================== 宠物相册 ====================

@router.get("/{pet_id}/photos", summary="获取宠物相册")
async def get_pet_photos(
    pet_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物的照片列表"""
    # 验证宠物存在
    pet = db.query(Pet).filter(Pet.id == pet_id, Pet.deleted_at.is_(None)).first()
    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    query = db.query(PetPhoto).filter(
        PetPhoto.pet_id == pet_id,
        PetPhoto.deleted_at.is_(None)
    ).order_by(desc(PetPhoto.created_at))

    total = query.count()
    photos = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[p.to_dict() for p in photos],
        page=page,
        page_size=page_size,
        total=total
    )


@router.post("/{pet_id}/photos", summary="添加宠物照片")
async def add_pet_photo(
    pet_id: int,
    request: AddPhotoRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加宠物照片"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    # 清理描述
    description = sanitize_text(request.description, max_length=500) if request.description else None

    photo = PetPhoto(
        pet_id=pet_id,
        user_id=current_user.id,
        url=request.url,
        thumbnail_url=request.thumbnail_url,
        description=description,
        taken_at=request.taken_at,
        is_avatar=request.is_avatar
    )
    db.add(photo)

    # 如果设为头像，更新宠物头像并取消其他照片的头像标记
    if request.is_avatar:
        db.query(PetPhoto).filter(
            PetPhoto.pet_id == pet_id,
            PetPhoto.is_avatar == True
        ).update({"is_avatar": False})
        pet.avatar_url = request.url

    db.commit()
    db.refresh(photo)

    return success(data=photo.to_dict(), message="照片添加成功")


@router.delete("/{pet_id}/photos/{photo_id}", summary="删除宠物照片")
async def delete_pet_photo(
    pet_id: int,
    photo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除宠物照片"""
    photo = db.query(PetPhoto).filter(
        PetPhoto.id == photo_id,
        PetPhoto.pet_id == pet_id,
        PetPhoto.user_id == current_user.id,
        PetPhoto.deleted_at.is_(None)
    ).first()

    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")

    photo.deleted_at = datetime.now()
    db.commit()

    return success(message="删除成功")


# ==================== 疫苗记录 ====================

@router.get("/{pet_id}/vaccinations", summary="获取疫苗记录")
async def get_vaccinations(
    pet_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物的疫苗接种记录"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    query = db.query(VaccinationRecord).filter(
        VaccinationRecord.pet_id == pet_id
    ).order_by(desc(VaccinationRecord.vaccination_date))

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[r.to_dict() for r in records],
        page=page,
        page_size=page_size,
        total=total
    )


@router.post("/{pet_id}/vaccinations", summary="添加疫苗记录")
async def add_vaccination(
    pet_id: int,
    request: AddVaccinationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加疫苗接种记录"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    # 清理输入
    notes = sanitize_text(request.notes, max_length=1000) if request.notes else None

    record = VaccinationRecord(
        pet_id=pet_id,
        vaccine_name=sanitize_text(request.vaccine_name, max_length=100),
        vaccine_type=request.vaccine_type,
        manufacturer=request.manufacturer,
        batch_number=request.batch_number,
        vaccination_date=request.vaccination_date,
        next_date=request.next_date,
        expiry_date=request.expiry_date,
        hospital_name=request.hospital_name,
        doctor_name=request.doctor_name,
        cost=request.cost,
        notes=notes,
        certificate_url=request.certificate_url,
        reminder_enabled=request.reminder_enabled,
        reminder_days_before=request.reminder_days_before
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return success(data=record.to_dict(), message="疫苗记录添加成功")


@router.put("/{pet_id}/vaccinations/{record_id}", summary="更新疫苗记录")
async def update_vaccination(
    pet_id: int,
    record_id: int,
    request: UpdateVaccinationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新疫苗接种记录"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    record = db.query(VaccinationRecord).filter(
        VaccinationRecord.id == record_id,
        VaccinationRecord.pet_id == pet_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="疫苗记录不存在")

    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(record, key, value)

    db.commit()
    db.refresh(record)

    return success(data=record.to_dict(), message="更新成功")


@router.delete("/{pet_id}/vaccinations/{record_id}", summary="删除疫苗记录")
async def delete_vaccination(
    pet_id: int,
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除疫苗接种记录"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    record = db.query(VaccinationRecord).filter(
        VaccinationRecord.id == record_id,
        VaccinationRecord.pet_id == pet_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="疫苗记录不存在")

    db.delete(record)
    db.commit()

    return success(message="删除成功")


# ==================== 体重记录 ====================

@router.get("/{pet_id}/weights", summary="获取体重记录")
async def get_weight_records(
    pet_id: int,
    days: int = Query(90, ge=7, le=365, description="获取最近几天的记录"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物的体重记录（用于绘制体重曲线）"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    start_date = date.today() - timedelta(days=days)

    records = db.query(WeightRecord).filter(
        WeightRecord.pet_id == pet_id,
        WeightRecord.record_date >= start_date
    ).order_by(WeightRecord.record_date).all()

    # 计算统计数据
    if records:
        weights = [r.weight for r in records]
        stats = {
            "min": min(weights),
            "max": max(weights),
            "avg": round(sum(weights) / len(weights), 2),
            "latest": records[-1].weight,
            "trend": round(records[-1].weight - records[0].weight, 2) if len(records) > 1 else 0
        }
    else:
        stats = None

    return success(data={
        "records": [r.to_dict() for r in records],
        "stats": stats
    })


@router.post("/{pet_id}/weights", summary="添加体重记录")
async def add_weight_record(
    pet_id: int,
    request: AddWeightRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """添加体重记录"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    # 检查同一天是否已有记录
    existing = db.query(WeightRecord).filter(
        WeightRecord.pet_id == pet_id,
        WeightRecord.record_date == request.record_date
    ).first()

    if existing:
        # 更新现有记录
        existing.weight = request.weight
        existing.notes = sanitize_text(request.notes, max_length=500) if request.notes else None
        record = existing
    else:
        # 创建新记录
        record = WeightRecord(
            pet_id=pet_id,
            weight=request.weight,
            record_date=request.record_date,
            notes=sanitize_text(request.notes, max_length=500) if request.notes else None
        )
        db.add(record)

    # 更新宠物当前体重
    pet.weight = request.weight

    db.commit()
    db.refresh(record)

    return success(data=record.to_dict(), message="体重记录添加成功")


# ==================== 宠物统计 ====================

@router.get("/{pet_id}/statistics", summary="获取宠物统计")
async def get_pet_statistics(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取宠物的综合统计数据"""
    pet = db.query(Pet).filter(
        Pet.id == pet_id,
        Pet.owner_id == current_user.id,
        Pet.deleted_at.is_(None)
    ).first()

    if not pet:
        raise HTTPException(status_code=404, detail="宠物不存在")

    # 照片统计
    photos_count = db.query(func.count(PetPhoto.id)).filter(
        PetPhoto.pet_id == pet_id,
        PetPhoto.deleted_at.is_(None)
    ).scalar()

    # 疫苗统计
    vaccinations_count = db.query(func.count(VaccinationRecord.id)).filter(
        VaccinationRecord.pet_id == pet_id
    ).scalar()

    # 体重统计
    weight_records_count = db.query(func.count(WeightRecord.id)).filter(
        WeightRecord.pet_id == pet_id
    ).scalar()

    # 最新体重和30天变化
    latest_weight = db.query(WeightRecord).filter(
        WeightRecord.pet_id == pet_id
    ).order_by(desc(WeightRecord.record_date)).first()

    weight_30d_ago = db.query(WeightRecord).filter(
        WeightRecord.pet_id == pet_id,
        WeightRecord.record_date <= date.today() - timedelta(days=30)
    ).order_by(desc(WeightRecord.record_date)).first()

    weight_change_30d = None
    if latest_weight and weight_30d_ago:
        weight_change_30d = round(latest_weight.weight - weight_30d_ago.weight, 2)

    # 即将到期的疫苗（未来30天）
    upcoming_vaccinations = db.query(VaccinationRecord).filter(
        VaccinationRecord.pet_id == pet_id,
        VaccinationRecord.next_date.isnot(None),
        VaccinationRecord.next_date >= date.today(),
        VaccinationRecord.next_date <= date.today() + timedelta(days=30)
    ).order_by(VaccinationRecord.next_date).all()

    return success(data={
        "total_photos": photos_count,
        "total_vaccinations": vaccinations_count,
        "total_weight_records": weight_records_count,
        "latest_weight": latest_weight.weight if latest_weight else None,
        "weight_change_30d": weight_change_30d,
        "upcoming_vaccinations": [v.to_dict() for v in upcoming_vaccinations],
        "pet_age_months": pet.age_months,
        "days_with_us": (date.today() - pet.adoption_date).days if pet.adoption_date else None
    })


# ==================== 品种查询 ====================

@router.get("/breeds/list", summary="获取品种列表")
async def get_breeds(
    pet_type: str = Query(None, description="宠物类型: dog cat bird fish other"),
    keyword: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取宠物品种列表"""
    query = db.query(PetBreed)

    if pet_type:
        query = query.filter(PetBreed.pet_type == pet_type)

    if keyword:
        # 安全处理搜索关键词
        safe_keyword = sanitize_search_query(keyword, max_length=50)
        if safe_keyword:
            query = query.filter(
                (PetBreed.name.contains(safe_keyword)) |
                (PetBreed.name_en.contains(safe_keyword))
            )

    total = query.count()
    breeds = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[{
            "id": b.id,
            "pet_type": b.pet_type,
            "name": b.name,
            "name_en": b.name_en,
            "image_url": b.image_url,
            "character": b.character
        } for b in breeds],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/breeds/{breed_id}", summary="获取品种详情")
async def get_breed(breed_id: int, db: Session = Depends(get_db)):
    """获取品种详细信息"""
    breed = db.query(PetBreed).filter(PetBreed.id == breed_id).first()
    if not breed:
        raise HTTPException(status_code=404, detail="品种不存在")

    return success(data={
        "id": breed.id,
        "pet_type": breed.pet_type,
        "name": breed.name,
        "name_en": breed.name_en,
        "description": breed.description,
        "origin": breed.origin,
        "life_span": breed.life_span,
        "weight_range": breed.weight_range,
        "character": breed.character,
        "care_tips": breed.care_tips,
        "common_diseases": breed.common_diseases,
        "diet_tips": breed.diet_tips,
        "exercise_needs": breed.exercise_needs,
        "grooming_needs": breed.grooming_needs,
        "image_url": breed.image_url
    })
