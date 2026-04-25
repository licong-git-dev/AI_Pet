"""
PetPal - 宠物模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, Date, ForeignKey, Float, func, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class PetPhoto(Base):
    """宠物相册表"""
    __tablename__ = "pet_photos"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="照片ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True, comment="宠物ID")
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="上传用户ID")

    url = Column(String(500), nullable=False, comment="图片URL")
    thumbnail_url = Column(String(500), nullable=True, comment="缩略图URL")
    description = Column(String(500), nullable=True, comment="图片描述")

    # 图片信息
    file_size = Column(Integer, nullable=True, comment="文件大小(bytes)")
    width = Column(Integer, nullable=True, comment="图片宽度")
    height = Column(Integer, nullable=True, comment="图片高度")
    mime_type = Column(String(50), nullable=True, comment="MIME类型")

    # 标记
    is_avatar = Column(Boolean, default=False, comment="是否为头像")
    is_cover = Column(Boolean, default=False, comment="是否为封面")

    # 统计
    likes_count = Column(Integer, default=0, comment="点赞数")

    taken_at = Column(DateTime, nullable=True, comment="拍摄时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    def to_dict(self):
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "description": self.description,
            "is_avatar": self.is_avatar,
            "is_cover": self.is_cover,
            "likes_count": self.likes_count,
            "taken_at": self.taken_at.isoformat() if self.taken_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class VaccinationRecord(Base):
    """疫苗接种记录表"""
    __tablename__ = "vaccination_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True, comment="宠物ID")

    vaccine_name = Column(String(100), nullable=False, comment="疫苗名称")
    vaccine_type = Column(String(50), nullable=True, comment="疫苗类型: core核心 non_core非核心 rabies狂犬")
    manufacturer = Column(String(100), nullable=True, comment="生产厂家")
    batch_number = Column(String(100), nullable=True, comment="批次号")

    vaccination_date = Column(Date, nullable=False, comment="接种日期")
    next_date = Column(Date, nullable=True, comment="下次接种日期")
    expiry_date = Column(Date, nullable=True, comment="疫苗有效期")

    hospital_name = Column(String(200), nullable=True, comment="接种医院")
    doctor_name = Column(String(100), nullable=True, comment="接种医生")
    cost = Column(Float, nullable=True, comment="费用")

    notes = Column(Text, nullable=True, comment="备注")
    certificate_url = Column(String(500), nullable=True, comment="接种证明图片")

    # 提醒设置
    reminder_enabled = Column(Boolean, default=True, comment="是否开启提醒")
    reminder_days_before = Column(Integer, default=7, comment="提前几天提醒")
    reminder_sent = Column(Boolean, default=False, comment="是否已发送提醒")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "vaccine_name": self.vaccine_name,
            "vaccine_type": self.vaccine_type,
            "manufacturer": self.manufacturer,
            "batch_number": self.batch_number,
            "vaccination_date": self.vaccination_date.isoformat() if self.vaccination_date else None,
            "next_date": self.next_date.isoformat() if self.next_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "hospital_name": self.hospital_name,
            "doctor_name": self.doctor_name,
            "cost": self.cost,
            "notes": self.notes,
            "certificate_url": self.certificate_url,
            "reminder_enabled": self.reminder_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class WeightRecord(Base):
    """体重记录表（用于绘制体重曲线）"""
    __tablename__ = "weight_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    pet_id = Column(BigInteger, ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, index=True, comment="宠物ID")

    weight = Column(Float, nullable=False, comment="体重(kg)")
    record_date = Column(Date, nullable=False, comment="记录日期")
    notes = Column(String(500), nullable=True, comment="备注")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    def to_dict(self):
        return {
            "id": self.id,
            "pet_id": self.pet_id,
            "weight": self.weight,
            "record_date": self.record_date.isoformat() if self.record_date else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class PetBreed(Base):
    """宠物品种表"""
    __tablename__ = "pet_breeds"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="品种ID")
    pet_type = Column(String(20), nullable=False, index=True, comment="宠物类型: dog狗 cat猫 bird鸟 fish鱼 other其他")
    name = Column(String(100), nullable=False, comment="品种名称")
    name_en = Column(String(100), nullable=True, comment="英文名称")
    description = Column(Text, nullable=True, comment="品种描述")
    origin = Column(String(100), nullable=True, comment="原产地")
    life_span = Column(String(50), nullable=True, comment="寿命范围")
    weight_range = Column(String(50), nullable=True, comment="体重范围")
    character = Column(Text, nullable=True, comment="性格特点")
    care_tips = Column(Text, nullable=True, comment="养护要点")
    common_diseases = Column(Text, nullable=True, comment="常见疾病")
    diet_tips = Column(Text, nullable=True, comment="饮食建议")
    exercise_needs = Column(String(20), nullable=True, comment="运动需求: low低 medium中 high高")
    grooming_needs = Column(String(20), nullable=True, comment="美容需求: low低 medium中 high高")
    image_url = Column(String(500), nullable=True, comment="品种图片")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Pet(Base):
    """宠物档案表"""
    __tablename__ = "pets"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="宠物ID")
    owner_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="主人ID")
    breed_id = Column(BigInteger, ForeignKey("pet_breeds.id", ondelete="SET NULL"), nullable=True, index=True, comment="品种ID")

    name = Column(String(100), nullable=False, comment="宠物名字")
    pet_type = Column(String(20), nullable=False, index=True, comment="宠物类型: dog狗 cat猫 bird鸟 fish鱼 other其他")
    breed_name = Column(String(100), nullable=True, comment="品种名称(冗余)")
    avatar_url = Column(String(500), nullable=True, comment="宠物头像")

    # 基本信息
    gender = Column(Integer, default=0, comment="性别: 0未知 1公 2母")
    birthday = Column(Date, nullable=True, comment="生日")
    adoption_date = Column(Date, nullable=True, comment="领养日期")
    weight = Column(Float, nullable=True, comment="体重(kg)")

    # 健康信息
    is_neutered = Column(Integer, default=0, comment="是否绝育: 0否 1是")
    health_status = Column(String(20), default="healthy", comment="健康状态: healthy健康 sick生病 recovering康复中")
    allergies = Column(Text, nullable=True, comment="过敏信息(JSON)")
    medical_history = Column(Text, nullable=True, comment="病史记录(JSON)")
    vaccination_records = Column(Text, nullable=True, comment="疫苗记录(JSON)")

    # 性格特点
    personality = Column(Text, nullable=True, comment="性格特点(JSON数组)")

    # 统计
    posts_count = Column(Integer, default=0, comment="相关帖子数")
    fans_count = Column(Integer, default=0, comment="粉丝数")

    # 状态
    status = Column(Integer, default=1, comment="状态: 1正常 2已转让 3已离世")

    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    # 关系
    owner = relationship("User", back_populates="pets")
    breed = relationship("PetBreed")
    photos = relationship("PetPhoto", backref="pet", lazy="dynamic")
    vaccinations = relationship("VaccinationRecord", backref="pet", lazy="dynamic")
    weight_records = relationship("WeightRecord", backref="pet", lazy="dynamic")

    @property
    def age(self):
        """计算宠物年龄"""
        if not self.birthday:
            return None
        from datetime import date
        today = date.today()
        years = today.year - self.birthday.year
        if today.month < self.birthday.month or (today.month == self.birthday.month and today.day < self.birthday.day):
            years -= 1
        return years

    @property
    def age_months(self):
        """计算宠物月龄"""
        if not self.birthday:
            return None
        from datetime import date
        today = date.today()
        months = (today.year - self.birthday.year) * 12 + (today.month - self.birthday.month)
        if today.day < self.birthday.day:
            months -= 1
        return max(0, months)

    @property
    def photos_count(self):
        """获取照片数量"""
        return self.photos.filter(PetPhoto.deleted_at.is_(None)).count() if self.photos else 0

    def to_dict(self, include_stats: bool = False):
        """转换为字典"""
        data = {
            "id": self.id,
            "name": self.name,
            "pet_type": self.pet_type,
            "breed_name": self.breed_name,
            "avatar_url": self.avatar_url,
            "gender": self.gender,
            "birthday": self.birthday.isoformat() if self.birthday else None,
            "age": self.age,
            "age_months": self.age_months,
            "weight": self.weight,
            "is_neutered": self.is_neutered,
            "health_status": self.health_status,
            "personality": self.personality,
            "posts_count": self.posts_count,
            "fans_count": self.fans_count,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

        if include_stats:
            data["photos_count"] = self.photos_count
            data["vaccinations_count"] = self.vaccinations.count() if self.vaccinations else 0

        return data
