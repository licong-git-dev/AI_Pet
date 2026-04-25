"""
PetPal - 健康相关Schema
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class HealthAnalysisRequest(BaseModel):
    """健康分析请求"""
    pet_id: int = Field(..., description="宠物ID")
    images: List[str] = Field(..., description="宠物图片URL列表")
    description: Optional[str] = Field(None, max_length=1000, description="补充描述")
    analysis_type: str = Field("general", description="分析类型")


class HealthAnalysisResponse(BaseModel):
    """健康分析响应"""
    health_score: int = Field(..., description="健康评分(0-100)")
    risk_level: str = Field(..., description="风险等级: low medium high")
    analysis_result: dict = Field(..., description="分析结果详情")
    suggestions: List[str] = Field(..., description="建议列表")


class ConsultationRequest(BaseModel):
    """问诊请求"""
    pet_id: int = Field(..., description="宠物ID")
    chief_complaint: str = Field(..., max_length=500, description="主诉")
    symptoms: Optional[str] = Field(None, max_length=2000, description="症状描述")
    duration: Optional[str] = Field(None, max_length=100, description="症状持续时间")
    image_urls: Optional[List[str]] = Field(None, description="图片URL列表")


class ConsultationMessageRequest(BaseModel):
    """问诊消息请求"""
    content: str = Field(..., max_length=2000, description="消息内容")
    image_urls: Optional[List[str]] = Field(None, description="图片URL列表")


class CreateHealthRecordRequest(BaseModel):
    """创建健康记录请求"""
    pet_id: int = Field(..., description="宠物ID")
    record_type: str = Field(..., description="记录类型: checkup vaccination deworming weight diet exercise")
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = Field(None, max_length=2000)
    images: Optional[str] = Field(None, description="图片URL列表(JSON)")
    weight: Optional[float] = Field(None, gt=0)
    temperature: Optional[float] = None
    vaccine_name: Optional[str] = Field(None, max_length=100)
    next_date: Optional[datetime] = None
    record_date: Optional[datetime] = None
