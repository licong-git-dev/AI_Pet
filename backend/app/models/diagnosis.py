"""
PetPal - AI健康诊断模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, Float, func, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class HealthDiagnosis(Base):
    """AI健康诊断记录表"""
    __tablename__ = "health_diagnoses"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="诊断ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True, comment="宠物ID")

    # 诊断类型: skin皮肤 eye眼睛 mouth口腔 feces粪便 symptom症状描述
    diagnosis_type = Column(String(20), nullable=False, comment="诊断类型")

    # 用户输入
    image_url = Column(Text, nullable=True, comment="上传的图片URL")
    symptom_desc = Column(Text, nullable=True, comment="用户补充的症状描述")

    # AI诊断结果
    health_score = Column(Integer, nullable=True, comment="健康评分(0-100)")
    risk_level = Column(String(20), nullable=True, comment="风险等级: low/medium/high/urgent")
    ai_analysis = Column(JSON, nullable=True, comment="AI分析结果JSON")
    suggestions = Column(JSON, nullable=True, comment="建议措施JSON")

    # AI模型信息
    ai_model = Column(String(50), default="qwen-vl-max", comment="使用的AI模型")
    confidence = Column(Float, nullable=True, comment="总体置信度(0-1)")

    # 状态
    status = Column(String(20), default="completed", comment="状态: pending/processing/completed/failed")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 关系
    conversations = relationship("DiagnosisConversation", back_populates="diagnosis", cascade="all, delete-orphan")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "pet_id": self.pet_id,
            "diagnosis_type": self.diagnosis_type,
            "image_url": self.image_url,
            "symptom_desc": self.symptom_desc,
            "health_score": self.health_score,
            "risk_level": self.risk_level,
            "ai_analysis": self.ai_analysis,
            "suggestions": self.suggestions,
            "ai_model": self.ai_model,
            "confidence": self.confidence,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class DiagnosisConversation(Base):
    """诊断问诊对话表"""
    __tablename__ = "diagnosis_conversations"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="消息ID")
    diagnosis_id = Column(BigInteger, ForeignKey("health_diagnoses.id", ondelete="CASCADE"), nullable=False, index=True, comment="诊断ID")

    role = Column(String(20), nullable=False, comment="角色: user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    # 关系
    diagnosis = relationship("HealthDiagnosis", back_populates="conversations")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "diagnosis_id": self.diagnosis_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
