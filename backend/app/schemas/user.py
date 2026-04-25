"""
PetPal - 用户相关Schema

包含：
- 用户信息
- 用户设置
- 收货地址
- 反馈举报
"""
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator
import re


# ==================== 用户信息 ====================

class UserProfile(BaseModel):
    """用户公开信息"""
    id: int
    phone: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    gender: int = 0
    bio: Optional[str] = None
    member_level: int = 0
    points: int = 0
    followers_count: int = 0
    following_count: int = 0
    likes_count: int = 0
    posts_count: int = 0
    role: str = "user"
    is_following: Optional[bool] = None
    is_blocked: Optional[bool] = None


class UpdateProfileRequest(BaseModel):
    """更新用户信息请求"""
    nickname: Optional[str] = Field(None, min_length=1, max_length=100)
    avatar_url: Optional[str] = Field(None, max_length=500)
    gender: Optional[int] = Field(None, ge=0, le=2)
    birthday: Optional[date] = None
    bio: Optional[str] = Field(None, max_length=500)
    email: Optional[str] = Field(None, max_length=255)

    @field_validator('nickname')
    @classmethod
    def validate_nickname(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('昵称不能为空')
            # 过滤敏感词（简单示例）
            forbidden = ['admin', 'administrator', '管理员', '官方']
            for word in forbidden:
                if word.lower() in v.lower():
                    raise ValueError('昵称包含禁用词')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v is not None:
            v = v.strip().lower()
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
                raise ValueError('邮箱格式不正确')
        return v


class UserStatistics(BaseModel):
    """用户统计数据"""
    pets_count: int = 0
    posts_count: int = 0
    comments_count: int = 0
    likes_count: int = 0
    followers_count: int = 0
    following_count: int = 0
    health_records_count: int = 0
    consultations_count: int = 0
    points: int = 0
    member_level: int = 0
    member_expire_at: Optional[datetime] = None
    days_joined: int = 0


class UserDetailProfile(UserProfile):
    """用户详细信息（含统计）"""
    statistics: Optional[UserStatistics] = None
    recent_posts: Optional[List[Dict[str, Any]]] = None
    recent_pets: Optional[List[Dict[str, Any]]] = None


# ==================== 用户设置 ====================

class PrivacySettings(BaseModel):
    """隐私设置"""
    profile_visibility: str = Field("public", pattern="^(public|followers|private)$")
    show_online_status: bool = True
    show_pet_list: bool = True
    allow_stranger_message: bool = True
    allow_comment: bool = True
    show_location: bool = False


class NotificationSettings(BaseModel):
    """通知设置"""
    like: bool = True
    comment: bool = True
    follow: bool = True
    message: bool = True
    system: bool = True
    activity: bool = True
    health_reminder: bool = True


class PushSettings(BaseModel):
    """推送设置"""
    enabled: bool = True
    quiet_start: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    quiet_end: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")


class DisplaySettings(BaseModel):
    """显示设置"""
    language: str = Field("zh-CN", max_length=10)
    theme: str = Field("light", pattern="^(light|dark|auto)$")
    font_size: str = Field("medium", pattern="^(small|medium|large)$")


class UserSettingsResponse(BaseModel):
    """用户设置响应"""
    privacy: PrivacySettings
    notifications: NotificationSettings
    push: PushSettings
    display: DisplaySettings


class UpdatePrivacyRequest(BaseModel):
    """更新隐私设置请求"""
    profile_visibility: Optional[str] = Field(None, pattern="^(public|followers|private)$")
    show_online_status: Optional[bool] = None
    show_pet_list: Optional[bool] = None
    allow_stranger_message: Optional[bool] = None
    allow_comment: Optional[bool] = None
    show_location: Optional[bool] = None


class UpdateNotificationRequest(BaseModel):
    """更新通知设置请求"""
    like: Optional[bool] = None
    comment: Optional[bool] = None
    follow: Optional[bool] = None
    message: Optional[bool] = None
    system: Optional[bool] = None
    activity: Optional[bool] = None
    health_reminder: Optional[bool] = None


class UpdatePushRequest(BaseModel):
    """更新推送设置请求"""
    enabled: Optional[bool] = None
    quiet_start: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    quiet_end: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")


class UpdateDisplayRequest(BaseModel):
    """更新显示设置请求"""
    language: Optional[str] = Field(None, max_length=10)
    theme: Optional[str] = Field(None, pattern="^(light|dark|auto)$")
    font_size: Optional[str] = Field(None, pattern="^(small|medium|large)$")


# ==================== 收货地址 ====================

class AddressCreate(BaseModel):
    """创建收货地址"""
    receiver_name: str = Field(..., min_length=2, max_length=50)
    receiver_phone: str = Field(..., pattern="^1[3-9]\\d{9}$")
    province: str = Field(..., min_length=2, max_length=50)
    city: str = Field(..., min_length=2, max_length=50)
    district: str = Field(..., min_length=2, max_length=50)
    detail_address: str = Field(..., min_length=5, max_length=200)
    postal_code: Optional[str] = Field(None, pattern="^\\d{6}$")
    tag: Optional[str] = Field(None, pattern="^(home|company)$")
    is_default: bool = False


class AddressUpdate(BaseModel):
    """更新收货地址"""
    receiver_name: Optional[str] = Field(None, min_length=2, max_length=50)
    receiver_phone: Optional[str] = Field(None, pattern="^1[3-9]\\d{9}$")
    province: Optional[str] = Field(None, min_length=2, max_length=50)
    city: Optional[str] = Field(None, min_length=2, max_length=50)
    district: Optional[str] = Field(None, min_length=2, max_length=50)
    detail_address: Optional[str] = Field(None, min_length=5, max_length=200)
    postal_code: Optional[str] = Field(None, pattern="^\\d{6}$")
    tag: Optional[str] = Field(None, pattern="^(home|company)$")
    is_default: Optional[bool] = None


class AddressResponse(BaseModel):
    """收货地址响应"""
    id: int
    receiver_name: str
    receiver_phone: str
    province: str
    city: str
    district: str
    detail_address: str
    full_address: str
    postal_code: Optional[str] = None
    tag: Optional[str] = None
    is_default: bool = False


# ==================== 用户反馈 ====================

class FeedbackCreate(BaseModel):
    """创建用户反馈"""
    feedback_type: str = Field(..., pattern="^(bug|suggestion|complaint|other)$")
    content: str = Field(..., min_length=10, max_length=2000)
    images: Optional[List[str]] = Field(None, max_length=5)
    contact: Optional[str] = Field(None, max_length=100)

    @field_validator('images')
    @classmethod
    def validate_images(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError('最多上传5张图片')
        return v


class FeedbackResponse(BaseModel):
    """反馈响应"""
    id: int
    feedback_type: str
    content: str
    images: List[str] = []
    status: str
    reply: Optional[str] = None
    replied_at: Optional[datetime] = None
    created_at: datetime


# ==================== 用户举报 ====================

class ReportCreate(BaseModel):
    """创建举报"""
    target_type: str = Field(..., pattern="^(user|post|comment|message)$")
    target_id: int = Field(..., gt=0)
    reason: str = Field(..., pattern="^(spam|abuse|porn|fraud|other)$")
    description: Optional[str] = Field(None, max_length=500)
    evidence_images: Optional[List[str]] = Field(None, max_length=5)

    @field_validator('evidence_images')
    @classmethod
    def validate_images(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError('最多上传5张证据图片')
        return v


class ReportResponse(BaseModel):
    """举报响应"""
    id: int
    target_type: str
    target_id: int
    reason: str
    description: Optional[str] = None
    status: str
    created_at: datetime


# ==================== 黑名单 ====================

class BlockUserRequest(BaseModel):
    """拉黑用户请求"""
    user_id: int = Field(..., gt=0)
    reason: Optional[str] = Field(None, max_length=200)


class BlockedUserResponse(BaseModel):
    """被拉黑用户信息"""
    id: int
    user_id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    reason: Optional[str] = None
    blocked_at: datetime


# ==================== 用户搜索 ====================

class SearchUsersRequest(BaseModel):
    """搜索用户请求"""
    keyword: str = Field(..., min_length=1, max_length=50)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class SearchUserResult(BaseModel):
    """搜索用户结果"""
    id: int
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    followers_count: int = 0
    is_following: bool = False
