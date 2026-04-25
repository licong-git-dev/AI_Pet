"""
PetPal - 认证相关Schema
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import re


class SendCodeRequest(BaseModel):
    """发送验证码请求"""
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="手机号")


class LoginRequest(BaseModel):
    """验证码登录请求"""
    phone: str = Field(..., description="手机号")
    code: str = Field(..., min_length=4, max_length=6, description="验证码")


class PasswordLoginRequest(BaseModel):
    """密码登录请求"""
    phone: str = Field(..., description="手机号")
    password: str = Field(..., min_length=6, description="密码")
    captcha_id: Optional[str] = Field(None, description="图形验证码ID")
    captcha_code: Optional[str] = Field(None, description="图形验证码")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RegisterRequest(BaseModel):
    """注册请求"""
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="手机号")
    code: str = Field(..., min_length=4, max_length=6, description="验证码")
    nickname: Optional[str] = Field(None, max_length=100, description="昵称")
    password: Optional[str] = Field(None, min_length=6, description="密码")


class SetPasswordRequest(BaseModel):
    """设置密码请求（首次设置或已登录状态）"""
    password: str = Field(..., min_length=6, max_length=32, description="新密码")
    confirm_password: str = Field(..., description="确认密码")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        """验证密码强度"""
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        if len(v) > 32:
            raise ValueError("密码长度不能超过32位")
        # 至少包含数字和字母
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("两次输入的密码不一致")
        return v


class ChangePasswordRequest(BaseModel):
    """修改密码请求（需要旧密码）"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=32, description="新密码")
    confirm_password: str = Field(..., description="确认密码")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("两次输入的密码不一致")
        return v


class ResetPasswordRequest(BaseModel):
    """重置密码请求（通过短信验证码）"""
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="手机号")
    code: str = Field(..., min_length=4, max_length=6, description="短信验证码")
    new_password: str = Field(..., min_length=6, max_length=32, description="新密码")
    confirm_password: str = Field(..., description="确认密码")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        if not re.search(r"[0-9]", v):
            raise ValueError("密码必须包含数字")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("两次输入的密码不一致")
        return v

