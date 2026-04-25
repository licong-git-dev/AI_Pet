"""
PetPal - AI健康诊断Schema
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    """AI诊断请求"""
    pet_id: int = Field(..., description="宠物ID")
    diagnosis_type: str = Field(..., description="诊断类型: skin/eye/mouth/feces/symptom")
    image_base64: Optional[str] = Field(None, description="Base64编码的图片")
    symptom_desc: Optional[str] = Field(None, max_length=2000, description="症状描述")


class DiagnoseResponse(BaseModel):
    """AI诊断响应"""
    diagnosis_id: int = Field(..., description="诊断记录ID")
    health_score: int = Field(..., description="健康评分(0-100)")
    risk_level: str = Field(..., description="风险等级: low/medium/high/urgent")
    ai_analysis: Dict[str, Any] = Field(..., description="AI分析结果")
    suggestions: Dict[str, Any] = Field(..., description="建议措施")


class DiagnosisChatRequest(BaseModel):
    """诊断对话请求"""
    message: str = Field(..., max_length=1000, description="用户消息")


class DiagnosisChatResponse(BaseModel):
    """诊断对话响应"""
    reply: str = Field(..., description="AI回复")
    conversation_id: int = Field(..., description="对话记录ID")


class DiagnosisHistoryItem(BaseModel):
    """诊断历史项"""
    id: int
    diagnosis_type: str
    health_score: Optional[int]
    risk_level: Optional[str]
    created_at: str
    pet_name: Optional[str] = None


class DiagnosisDetail(BaseModel):
    """诊断详情"""
    id: int
    user_id: int
    pet_id: int
    diagnosis_type: str
    image_url: Optional[str]
    symptom_desc: Optional[str]
    health_score: Optional[int]
    risk_level: Optional[str]
    ai_analysis: Optional[Dict[str, Any]]
    suggestions: Optional[Dict[str, Any]]
    confidence: Optional[float]
    status: str
    created_at: str
    conversations: Optional[List[Dict[str, Any]]] = None
