"""
PetPal - 宠物相关Schema
"""
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator
import re


class CreatePetRequest(BaseModel):
    """创建宠物请求"""
    name: str = Field(..., min_length=1, max_length=100, description="宠物名字")
    pet_type: str = Field(..., description="宠物类型: dog cat bird fish other")
    breed_id: Optional[int] = Field(None, description="品种ID")
    breed_name: Optional[str] = Field(None, max_length=100, description="品种名称")
    avatar_url: Optional[str] = Field(None, max_length=500)
    gender: Optional[int] = Field(0, ge=0, le=2, description="性别: 0未知 1公 2母")
    birthday: Optional[date] = None
    weight: Optional[float] = Field(None, gt=0, le=500, description="体重(kg)")
    is_neutered: Optional[int] = Field(0, ge=0, le=1)
    personality: Optional[str] = Field(None, description="性格特点(JSON)")

    @field_validator("pet_type")
    @classmethod
    def validate_pet_type(cls, v):
        allowed = ["dog", "cat", "bird", "fish", "rabbit", "hamster", "other"]
        if v not in allowed:
            raise ValueError(f"宠物类型必须是: {', '.join(allowed)}")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        # 移除危险字符
        v = re.sub(r'[<>"\';]', '', v.strip())
        if not v:
            raise ValueError("宠物名字不能为空")
        return v


class UpdatePetRequest(BaseModel):
    """更新宠物请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    breed_id: Optional[int] = None
    breed_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    gender: Optional[int] = Field(None, ge=0, le=2)
    birthday: Optional[date] = None
    weight: Optional[float] = Field(None, gt=0, le=500)
    is_neutered: Optional[int] = Field(None, ge=0, le=1)
    health_status: Optional[str] = Field(None, max_length=20)
    personality: Optional[str] = None
    allergies: Optional[str] = None
    medical_history: Optional[str] = None
    status: Optional[int] = Field(None, ge=1, le=3, description="状态: 1正常 2已转让 3已离世")

    @field_validator("health_status")
    @classmethod
    def validate_health_status(cls, v):
        if v and v not in ["healthy", "sick", "recovering"]:
            raise ValueError("健康状态必须是: healthy, sick, recovering")
        return v


class PetResponse(BaseModel):
    """宠物响应"""
    id: int
    name: str
    pet_type: str
    breed_name: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: int = 0
    birthday: Optional[date] = None
    age: Optional[int] = None
    age_months: Optional[int] = None
    weight: Optional[float] = None
    is_neutered: int = 0
    health_status: str = "healthy"
    posts_count: int = 0
    fans_count: int = 0
    photos_count: int = 0


# ==================== 宠物相册 ====================

class AddPhotoRequest(BaseModel):
    """添加照片请求"""
    url: str = Field(..., max_length=500, description="图片URL")
    thumbnail_url: Optional[str] = Field(None, max_length=500, description="缩略图URL")
    description: Optional[str] = Field(None, max_length=500, description="图片描述")
    taken_at: Optional[datetime] = Field(None, description="拍摄时间")
    is_avatar: bool = Field(False, description="设为头像")


class PhotoResponse(BaseModel):
    """照片响应"""
    id: int
    pet_id: int
    url: str
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    is_avatar: bool = False
    is_cover: bool = False
    likes_count: int = 0
    taken_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ==================== 疫苗记录 ====================

class AddVaccinationRequest(BaseModel):
    """添加疫苗记录请求"""
    vaccine_name: str = Field(..., min_length=1, max_length=100, description="疫苗名称")
    vaccine_type: Optional[str] = Field(None, description="疫苗类型: core non_core rabies")
    manufacturer: Optional[str] = Field(None, max_length=100, description="生产厂家")
    batch_number: Optional[str] = Field(None, max_length=100, description="批次号")
    vaccination_date: date = Field(..., description="接种日期")
    next_date: Optional[date] = Field(None, description="下次接种日期")
    expiry_date: Optional[date] = Field(None, description="疫苗有效期")
    hospital_name: Optional[str] = Field(None, max_length=200, description="接种医院")
    doctor_name: Optional[str] = Field(None, max_length=100, description="接种医生")
    cost: Optional[float] = Field(None, ge=0, description="费用")
    notes: Optional[str] = Field(None, max_length=1000, description="备注")
    certificate_url: Optional[str] = Field(None, max_length=500, description="接种证明图片")
    reminder_enabled: bool = Field(True, description="是否开启提醒")
    reminder_days_before: int = Field(7, ge=1, le=30, description="提前几天提醒")

    @field_validator("vaccine_type")
    @classmethod
    def validate_vaccine_type(cls, v):
        if v and v not in ["core", "non_core", "rabies"]:
            raise ValueError("疫苗类型必须是: core, non_core, rabies")
        return v


class UpdateVaccinationRequest(BaseModel):
    """更新疫苗记录请求"""
    vaccine_name: Optional[str] = Field(None, max_length=100)
    vaccine_type: Optional[str] = None
    manufacturer: Optional[str] = Field(None, max_length=100)
    batch_number: Optional[str] = Field(None, max_length=100)
    vaccination_date: Optional[date] = None
    next_date: Optional[date] = None
    expiry_date: Optional[date] = None
    hospital_name: Optional[str] = Field(None, max_length=200)
    doctor_name: Optional[str] = Field(None, max_length=100)
    cost: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = Field(None, max_length=1000)
    certificate_url: Optional[str] = Field(None, max_length=500)
    reminder_enabled: Optional[bool] = None
    reminder_days_before: Optional[int] = Field(None, ge=1, le=30)


class VaccinationResponse(BaseModel):
    """疫苗记录响应"""
    id: int
    pet_id: int
    vaccine_name: str
    vaccine_type: Optional[str] = None
    vaccination_date: date
    next_date: Optional[date] = None
    hospital_name: Optional[str] = None
    reminder_enabled: bool = True
    created_at: Optional[datetime] = None


# ==================== 体重记录 ====================

class AddWeightRequest(BaseModel):
    """添加体重记录请求"""
    weight: float = Field(..., gt=0, le=500, description="体重(kg)")
    record_date: date = Field(..., description="记录日期")
    notes: Optional[str] = Field(None, max_length=500, description="备注")


class WeightResponse(BaseModel):
    """体重记录响应"""
    id: int
    pet_id: int
    weight: float
    record_date: date
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


# ==================== 统计响应 ====================

class PetStatisticsResponse(BaseModel):
    """宠物统计响应"""
    total_photos: int = 0
    total_vaccinations: int = 0
    total_weight_records: int = 0
    latest_weight: Optional[float] = None
    weight_change_30d: Optional[float] = None
    upcoming_vaccinations: List[dict] = []
    health_score: Optional[int] = None
