"""
PetPal - 健康模型 (健康记录、问诊)
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey, Float, func
from sqlalchemy.orm import relationship
from app.database import Base


class HealthRecord(Base):
    """健康记录表"""
    __tablename__ = "health_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True, comment="宠物ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")

    record_type = Column(String(50), nullable=False, comment="记录类型: checkup体检 vaccination疫苗 deworming驱虫 weight体重 diet饮食 exercise运动 ai_analysis AI分析")

    # 体检/AI分析结果
    health_score = Column(Integer, nullable=True, comment="健康评分(0-100)")
    risk_level = Column(String(20), nullable=True, comment="风险等级: low低 medium中 high高")
    analysis_result = Column(Text, nullable=True, comment="AI分析结果(JSON)")
    ai_analysis = Column(Text, nullable=True, comment="AI分析详情")
    suggestions = Column(Text, nullable=True, comment="建议(JSON)")
    ai_suggestions = Column(Text, nullable=True, comment="AI建议详情")

    # 记录详情
    title = Column(String(200), nullable=True, comment="记录标题")
    content = Column(Text, nullable=True, comment="记录内容")
    description = Column(Text, nullable=True, comment="描述信息")
    images = Column(Text, nullable=True, comment="图片URL列表(JSON)")
    image_urls = Column(Text, nullable=True, comment="图片URL列表(兼容字段)")

    # 数值记录
    weight = Column(Float, nullable=True, comment="体重(kg)")
    temperature = Column(Float, nullable=True, comment="体温")

    # 疫苗/驱虫信息
    vaccine_name = Column(String(100), nullable=True, comment="疫苗名称")
    next_date = Column(DateTime, nullable=True, comment="下次时间")

    # 就诊信息
    hospital_name = Column(String(200), nullable=True, comment="医院名称")
    doctor_name = Column(String(100), nullable=True, comment="医生姓名")
    cost = Column(Float, nullable=True, comment="费用")

    record_date = Column(DateTime, nullable=True, comment="记录日期")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "record_type": self.record_type,
            "health_score": self.health_score,
            "risk_level": self.risk_level,
            "analysis_result": self.analysis_result,
            "ai_analysis": self.ai_analysis,
            "suggestions": self.suggestions,
            "ai_suggestions": self.ai_suggestions,
            "title": self.title,
            "content": self.content,
            "description": self.description,
            "images": self.images,
            "image_urls": self.image_urls,
            "weight": self.weight,
            "temperature": self.temperature,
            "vaccine_name": self.vaccine_name,
            "next_date": self.next_date.isoformat() if self.next_date else None,
            "hospital_name": self.hospital_name,
            "doctor_name": self.doctor_name,
            "cost": self.cost,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class HealthConsultation(Base):
    """健康咨询/问诊表"""
    __tablename__ = "health_consultations"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="咨询ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="SET NULL"), nullable=True, index=True, comment="宠物ID")

    consultation_type = Column(String(20), default="ai", comment="咨询类型: ai人工智能 expert专家")

    # 问诊信息
    title = Column(String(200), nullable=True, comment="问诊标题")
    chief_complaint = Column(Text, nullable=True, comment="主诉/主要问题")
    symptoms = Column(Text, nullable=True, comment="症状描述")
    symptom_duration = Column(String(100), nullable=True, comment="症状持续时间")
    duration = Column(String(100), nullable=True, comment="持续时间(兼容字段)")
    images = Column(Text, nullable=True, comment="图片URL列表(JSON)")
    videos = Column(Text, nullable=True, comment="视频URL列表(JSON)")

    # AI分析结果
    ai_diagnosis = Column(Text, nullable=True, comment="AI诊断结果(JSON)")
    ai_suggestions = Column(Text, nullable=True, comment="AI建议(JSON)")
    confidence_score = Column(Float, nullable=True, comment="置信度(0-1)")
    possible_diseases = Column(Text, nullable=True, comment="可能疾病(JSON)")
    urgency_level = Column(String(20), nullable=True, comment="紧急程度: low低 medium中 high高 urgent紧急")

    # 问诊总结
    summary = Column(Text, nullable=True, comment="问诊总结")
    diagnosis = Column(Text, nullable=True, comment="诊断结论")
    suggestions = Column(Text, nullable=True, comment="建议措施")

    # 专家咨询
    expert_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="专家ID")
    expert_reply = Column(Text, nullable=True, comment="专家回复")
    expert_reply_at = Column(DateTime, nullable=True, comment="专家回复时间")

    # 会话记录
    messages = Column(Text, nullable=True, comment="对话记录(JSON)")

    # 状态
    status = Column(String(20), default="pending", comment="状态: pending待处理 active进行中 processing处理中 completed已完成 closed已关闭")
    is_paid = Column(Integer, default=0, comment="是否付费: 0免费 1付费")
    price = Column(Float, default=0, comment="咨询费用")

    # 评价
    rating = Column(Integer, nullable=True, comment="评分(1-5)")
    feedback = Column(Text, nullable=True, comment="反馈")

    ended_at = Column(DateTime, nullable=True, comment="结束时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self, pet=None):
        """转换为字典"""
        data = {
            "id": self.id,
            "pet_id": self.pet_id,
            "consultation_type": self.consultation_type,
            "title": self.title,
            "chief_complaint": self.chief_complaint,
            "symptoms": self.symptoms,
            "symptom_duration": self.symptom_duration,
            "duration": self.duration,
            "images": self.images,
            "ai_diagnosis": self.ai_diagnosis,
            "ai_suggestions": self.ai_suggestions,
            "confidence_score": self.confidence_score,
            "possible_diseases": self.possible_diseases,
            "urgency_level": self.urgency_level,
            "summary": self.summary,
            "diagnosis": self.diagnosis,
            "suggestions": self.suggestions,
            "status": self.status,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        if pet is not None:
            data["pet"] = {
                "id": pet.id,
                "name": pet.name,
                "pet_type": pet.pet_type,
                "breed_name": pet.breed_name,
                "avatar_url": pet.avatar_url,
            }
        return data


class ConsultationMessage(Base):
    """问诊消息表"""
    __tablename__ = "consultation_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="消息ID")
    consultation_id = Column(BigInteger, ForeignKey("health_consultations.id", ondelete="CASCADE"), nullable=False, index=True, comment="问诊ID")
    role = Column(String(20), nullable=False, comment="角色: user用户 assistant助手")
    content = Column(Text, nullable=False, comment="消息内容")
    image_urls = Column(Text, nullable=True, comment="图片URL列表(JSON)")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "consultation_id": self.consultation_id,
            "role": self.role,
            "content": self.content,
            "image_urls": self.image_urls,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
