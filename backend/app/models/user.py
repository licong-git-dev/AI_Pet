"""
PetPal - 用户模型
"""
from datetime import datetime

from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, Date, func
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID")
    phone = Column(String(20), unique=True, nullable=False, index=True, comment="手机号")
    email = Column(String(255), unique=True, nullable=True, index=True, comment="邮箱")
    password = Column(String(255), nullable=True, comment="密码(BCrypt加密)")
    nickname = Column(String(100), nullable=True, comment="昵称")
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    gender = Column(Integer, default=0, comment="性别: 0未知 1男 2女")
    birthday = Column(Date, nullable=True, comment="生日")
    bio = Column(Text, nullable=True, comment="个人简介")

    # 会员相关
    member_level = Column(Integer, default=0, comment="会员等级: 0普通 1月度会员 2年度会员")
    member_expire_at = Column(DateTime, nullable=True, comment="会员过期时间")
    points = Column(Integer, default=0, comment="积分余额")

    # 社交统计
    followers_count = Column(Integer, default=0, comment="粉丝数")
    following_count = Column(Integer, default=0, comment="关注数")
    likes_count = Column(Integer, default=0, comment="获赞数")
    posts_count = Column(Integer, default=0, comment="发帖数")

    # 状态
    status = Column(Integer, default=1, comment="状态: 1正常 2禁用")
    role = Column(String(20), default="user", comment="角色: user普通用户 creator创作者 expert专家 admin管理员")

    # 登录信息
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    last_login_ip = Column(String(50), nullable=True, comment="最后登录IP")

    # 时间戳
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间(软删除)")

    # 关系
    pets = relationship("Pet", back_populates="owner", lazy="dynamic")
    posts = relationship("Post", back_populates="author", lazy="dynamic")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "phone": self.phone[:3] + "****" + self.phone[-4:] if self.phone else None,
            "email": self.email,
            "nickname": self.nickname,
            "avatar_url": self.avatar_url,
            "gender": self.gender,
            "bio": self.bio,
            "member_level": self.member_level,
            "member_expire_at": self.member_expire_at.isoformat() if self.member_expire_at else None,
            "is_member_active": bool(
                self.member_level > 0
                and self.member_expire_at
                and self.member_expire_at > datetime.now()
            ),
            "points": self.points,
            "followers_count": self.followers_count,
            "following_count": self.following_count,
            "likes_count": self.likes_count,
            "posts_count": self.posts_count,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
