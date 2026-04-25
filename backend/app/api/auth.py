"""
PetPal - 认证API

提供用户认证相关接口：
- 发送验证码
- 验证码登录
- 密码登录
- 注册账号
- 刷新Token
- 密码管理
- 退出登录
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    SendCodeRequest, LoginRequest, RegisterRequest,
    PasswordLoginRequest, SetPasswordRequest, ChangePasswordRequest,
    ResetPasswordRequest
)
from app.utils.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    refresh_tokens, revoke_user_tokens, get_user_active_sessions,
    verify_token, blacklist_token
)
from app.utils.response import success
from app.utils.deps import get_current_user
from app.config import settings
from app.services.sms_service import send_sms_code, verify_sms_code, get_rate_limit_ttl
from app.services.login_log_service import (
    record_login, check_login_risk, get_user_login_history,
    get_recent_login_locations
)
from app.services.captcha_service import create_captcha, verify_captcha

router = APIRouter()


# Pydantic模型
class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: Optional[str] = None


class LogoutRequest(BaseModel):
    """登出请求"""
    device_id: Optional[str] = None
    logout_all: bool = False


def get_client_ip(request: Request) -> str:
    """获取客户端真实IP地址

    支持通过代理获取真实IP
    """
    # 尝试从X-Forwarded-For获取
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # 取第一个IP（最原始的客户端IP）
        return forwarded_for.split(",")[0].strip()

    # 尝试从X-Real-IP获取
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # 直接获取客户端IP
    if request.client:
        return request.client.host

    return "127.0.0.1"


def get_user_agent(request: Request) -> str:
    """获取User-Agent"""
    return request.headers.get("User-Agent", "")


def set_refresh_cookie(response: JSONResponse, refresh_token: str) -> None:
    """设置Refresh Token Cookie"""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/"
    )


def clear_refresh_cookie(response: JSONResponse) -> None:
    """清理Refresh Token Cookie"""
    response.delete_cookie(key="refresh_token", path="/")


def build_auth_response(data: dict, message: str) -> JSONResponse:
    """构建带Refresh Cookie的认证响应"""
    response = JSONResponse(content=success(data=data, message=message))
    refresh_token = data.get("refresh_token")
    if refresh_token:
        set_refresh_cookie(response, refresh_token)
    return response


@router.post("/send-code", summary="发送验证码")
async def api_send_code(
    request: SendCodeRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    发送短信验证码

    - 验证码有效期5分钟
    - 同一手机号60秒内只能发送一次
    - 同一IP每小时最多发送10次
    - 同一手机号每天最多发送10次
    """
    phone = request.phone
    client_ip = get_client_ip(req)

    # 调用短信服务发送验证码
    success_flag, message, _ = await send_sms_code(phone, client_ip)

    if not success_flag:
        # 获取剩余等待时间
        wait_time = get_rate_limit_ttl(phone)
        raise HTTPException(
            status_code=429,
            detail=message,
            headers={"Retry-After": str(wait_time)} if wait_time > 0 else None
        )

    # 安全起见，无论环境均不返回验证码
    # 开发调试请查看控制台日志
    return success(message=message)


@router.post("/login", summary="验证码登录")
async def login(
    request: LoginRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    使用手机号和验证码登录

    - 新用户自动注册
    - 返回JWT Token
    - 记录登录日志和异地检测
    """
    phone = request.phone
    code = request.code
    client_ip = get_client_ip(req)
    user_agent = get_user_agent(req)

    # 检查登录风险
    risk_check = await check_login_risk(db, phone, client_ip)
    if not risk_check["allow"]:
        # 记录失败日志
        await record_login(
            db=db,
            user_id=None,
            phone=phone,
            login_ip=client_ip,
            user_agent=user_agent,
            login_type="sms",
            login_status=False,
            failure_reason=risk_check["message"]
        )
        raise HTTPException(status_code=429, detail=risk_check["message"])

    # 验证验证码
    verified, error_msg = verify_sms_code(phone, code)
    if not verified:
        # 记录失败日志
        user = db.query(User).filter(
            User.phone == phone,
            User.deleted_at.is_(None)
        ).first()
        await record_login(
            db=db,
            user_id=user.id if user else None,
            phone=phone,
            login_ip=client_ip,
            user_agent=user_agent,
            login_type="sms",
            login_status=False,
            failure_reason=error_msg
        )
        raise HTTPException(status_code=400, detail=error_msg)

    # 查找或创建用户
    user = db.query(User).filter(
        User.phone == phone,
        User.deleted_at.is_(None)
    ).first()

    is_new_user = False
    if not user:
        # 新用户注册
        is_new_user = True
        user = User(
            phone=phone,
            nickname=f"宠友{phone[-4:]}",
            status=1,
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 更新登录信息
    user.last_login_at = datetime.now()
    db.commit()

    # 记录成功登录日志
    login_log = await record_login(
        db=db,
        user_id=user.id,
        phone=phone,
        login_ip=client_ip,
        user_agent=user_agent,
        login_type="sms",
        login_status=True,
    )

    # 生成Token对
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token, _ = create_refresh_token(user_id=user.id)

    # 构建响应
    response_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,  # 秒
        "user": user.to_dict(),
        "is_new_user": is_new_user
    }

    # 如果检测到异地登录，添加警告
    if login_log.is_abnormal:
        response_data["security_warning"] = {
            "type": "abnormal_login",
            "message": f"检测到异地登录，当前位置：{login_log.login_location}",
            "risk_level": login_log.risk_level
        }

    return build_auth_response(
        data=response_data,
        message="登录成功" if not is_new_user else "注册并登录成功"
    )


@router.post("/register", summary="注册账号")
async def register(
    request: RegisterRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    注册新账号

    - 需要先发送验证码
    - 可以设置昵称和密码
    """
    phone = request.phone
    code = request.code
    client_ip = get_client_ip(req)
    user_agent = get_user_agent(req)

    # 验证验证码
    verified, error_msg = verify_sms_code(phone, code)
    if not verified:
        raise HTTPException(status_code=400, detail=error_msg)

    # 检查手机号是否已注册
    existing_user = db.query(User).filter(
        User.phone == phone,
        User.deleted_at.is_(None)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="该手机号已注册")

    # 创建用户
    user = User(
        phone=phone,
        nickname=request.nickname or f"宠友{phone[-4:]}",
        password=hash_password(request.password) if request.password else None,
        status=1,
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # 记录注册登录日志
    await record_login(
        db=db,
        user_id=user.id,
        phone=phone,
        login_ip=client_ip,
        user_agent=user_agent,
        login_type="register",
        login_status=True,
    )

    # 生成Token对
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token, _ = create_refresh_token(user_id=user.id)

    return build_auth_response(data={
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
        "user": user.to_dict()
    }, message="注册成功")


@router.post("/refresh", summary="刷新Token")
async def refresh_token_endpoint(req: Request, request: Optional[RefreshTokenRequest] = None):
    """使用Refresh Token刷新Access Token

    - Refresh Token只能使用一次（Token轮换）
    - 支持从请求体或 HttpOnly Cookie 读取 Refresh Token
    - 返回新的Access Token和Refresh Token
    """
    refresh_token_value = request.refresh_token if request and request.refresh_token else req.cookies.get("refresh_token")
    new_tokens = refresh_tokens(refresh_token_value) if refresh_token_value else None

    if not new_tokens:
        raise HTTPException(
            status_code=401,
            detail="Refresh Token无效或已过期",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return build_auth_response(data={
        "access_token": new_tokens["access_token"],
        "refresh_token": new_tokens["refresh_token"],
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }, message="Token刷新成功")


@router.post("/logout", summary="退出登录")
async def logout(
    request: Optional[LogoutRequest] = None,
    authorization: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user)
):
    """退出登录

    - 支持登出当前设备或所有设备
    - 会吊销相关的Refresh Token
    - 当前Access Token会被加入黑名单
    """
    # 吊销用户的Refresh Token
    if request and request.logout_all:
        # 登出所有设备
        revoke_user_tokens(current_user.id)
    elif request and request.device_id:
        # 登出指定设备
        revoke_user_tokens(current_user.id, request.device_id)
    else:
        # 登出当前设备（默认设备）
        revoke_user_tokens(current_user.id, "default")

    # 将当前Access Token加入黑名单
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        payload = verify_token(token)
        if payload and payload.get("jti"):
            blacklist_token(payload["jti"])

    response = JSONResponse(content=success(message="退出成功"))
    clear_refresh_cookie(response)
    return response


@router.get("/sessions", summary="获取活跃会话")
async def get_active_sessions(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有活跃会话

    - 用于多设备登录管理
    - 可以看到所有已登录的设备
    """
    sessions = get_user_active_sessions(current_user.id)
    return success(data={"sessions": sessions})


@router.get("/login-history", summary="获取登录历史")
async def get_login_history(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的登录历史记录

    - 包含登录时间、IP、设备、位置等信息
    - 用于用户安全审计
    """
    # 获取登录历史
    logs, total = await get_user_login_history(db, current_user.id, page, page_size)

    return success(data={
        "list": [log.to_dict() for log in logs],
        "total": total,
        "page": page,
        "page_size": page_size
    })


@router.get("/login-locations", summary="获取最近登录位置")
async def get_login_locations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取最近30天的登录位置

    - 用于展示用户登录地点分布
    - 帮助用户发现异常登录
    """
    locations = await get_recent_login_locations(db, current_user.id)

    return success(data={"locations": locations})


# ==================== 密码登录相关 ====================

@router.post("/login-password", summary="密码登录")
async def login_with_password(
    request: PasswordLoginRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """使用手机号和密码登录

    - 登录失败次数过多需要图形验证码
    - 记录登录日志和异地检测
    """
    phone = request.phone
    password = request.password
    client_ip = get_client_ip(req)
    user_agent = get_user_agent(req)

    # 检查登录风险
    risk_check = await check_login_risk(db, phone, client_ip)
    if not risk_check["allow"]:
        await record_login(
            db=db,
            user_id=None,
            phone=phone,
            login_ip=client_ip,
            user_agent=user_agent,
            login_type="password",
            login_status=False,
            failure_reason=risk_check["message"]
        )
        raise HTTPException(status_code=429, detail=risk_check["message"])

    # 如果需要图形验证码
    if risk_check.get("require_captcha"):
        if not request.captcha_id or not request.captcha_code:
            raise HTTPException(
                status_code=400,
                detail="登录失败次数过多，请输入图形验证码"
            )
        # 验证图形验证码
        captcha_valid, captcha_msg = verify_captcha(request.captcha_id, request.captcha_code)
        if not captcha_valid:
            raise HTTPException(status_code=400, detail=captcha_msg)

    # 查找用户
    user = db.query(User).filter(
        User.phone == phone,
        User.deleted_at.is_(None)
    ).first()

    if not user:
        await record_login(
            db=db,
            user_id=None,
            phone=phone,
            login_ip=client_ip,
            user_agent=user_agent,
            login_type="password",
            login_status=False,
            failure_reason="用户不存在"
        )
        raise HTTPException(status_code=400, detail="手机号或密码错误")

    # 检查是否设置了密码
    if not user.password:
        await record_login(
            db=db,
            user_id=user.id,
            phone=phone,
            login_ip=client_ip,
            user_agent=user_agent,
            login_type="password",
            login_status=False,
            failure_reason="未设置密码"
        )
        raise HTTPException(
            status_code=400,
            detail="您还未设置密码，请使用验证码登录后设置密码"
        )

    # 验证密码
    if not verify_password(password, user.password):
        await record_login(
            db=db,
            user_id=user.id,
            phone=phone,
            login_ip=client_ip,
            user_agent=user_agent,
            login_type="password",
            login_status=False,
            failure_reason="密码错误"
        )
        raise HTTPException(status_code=400, detail="手机号或密码错误")

    # 检查用户状态
    if user.status != 1:
        await record_login(
            db=db,
            user_id=user.id,
            phone=phone,
            login_ip=client_ip,
            user_agent=user_agent,
            login_type="password",
            login_status=False,
            failure_reason="账号已被禁用"
        )
        raise HTTPException(status_code=403, detail="账号已被禁用")

    # 更新登录信息
    user.last_login_at = datetime.now()
    db.commit()

    # 记录成功登录日志
    login_log = await record_login(
        db=db,
        user_id=user.id,
        phone=phone,
        login_ip=client_ip,
        user_agent=user_agent,
        login_type="password",
        login_status=True,
    )

    # 生成Token对
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token, _ = create_refresh_token(user_id=user.id)

    # 构建响应
    response_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
        "user": user.to_dict(),
    }

    # 如果检测到异地登录，添加警告
    if login_log.is_abnormal:
        response_data["security_warning"] = {
            "type": "abnormal_login",
            "message": f"检测到异地登录，当前位置：{login_log.login_location}",
            "risk_level": login_log.risk_level
        }

    return build_auth_response(data=response_data, message="登录成功")


@router.post("/set-password", summary="设置密码")
async def set_password(
    request: SetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """设置密码（首次设置或重新设置）

    - 需要已登录状态
    - 用于验证码登录后设置密码
    """
    # 检查是否已有密码
    if current_user.password:
        raise HTTPException(
            status_code=400,
            detail="您已设置密码，如需修改请使用修改密码功能"
        )

    # 设置密码
    current_user.password = hash_password(request.password)
    db.commit()

    return success(message="密码设置成功")


@router.post("/change-password", summary="修改密码")
async def change_password(
    request: ChangePasswordRequest,
    req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """修改密码

    - 需要验证旧密码
    - 修改成功后会吊销所有Token
    """
    # 检查是否设置了密码
    if not current_user.password:
        raise HTTPException(
            status_code=400,
            detail="您还未设置密码，请先设置密码"
        )

    # 验证旧密码
    if not verify_password(request.old_password, current_user.password):
        raise HTTPException(status_code=400, detail="旧密码错误")

    # 检查新密码不能与旧密码相同
    if verify_password(request.new_password, current_user.password):
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    # 更新密码
    current_user.password = hash_password(request.new_password)
    db.commit()

    # 吊销所有Token（安全措施）
    revoke_user_tokens(current_user.id)

    return success(message="密码修改成功，请重新登录")


@router.post("/reset-password", summary="重置密码")
async def reset_password(
    request: ResetPasswordRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """重置密码

    - 通过短信验证码重置
    - 重置成功后会吊销所有Token
    """
    phone = request.phone
    code = request.code

    # 验证验证码
    verified, error_msg = verify_sms_code(phone, code)
    if not verified:
        raise HTTPException(status_code=400, detail=error_msg)

    # 查找用户
    user = db.query(User).filter(
        User.phone == phone,
        User.deleted_at.is_(None)
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="用户不存在")

    # 更新密码
    user.password = hash_password(request.new_password)
    db.commit()

    # 吊销所有Token（安全措施）
    revoke_user_tokens(user.id)

    return success(message="密码重置成功，请使用新密码登录")


@router.get("/has-password", summary="检查是否设置密码")
async def check_has_password(
    current_user: User = Depends(get_current_user)
):
    """检查当前用户是否设置了密码"""
    return success(data={"has_password": bool(current_user.password)})


# ==================== 图形验证码相关 ====================

@router.get("/captcha", summary="获取图形验证码")
async def get_captcha():
    """获取图形验证码

    - 返回验证码ID和Base64编码的图片
    - 验证码有效期5分钟
    - 用于登录失败次数过多等场景
    """
    import base64

    captcha_id, code, image_bytes = create_captcha()

    # 转为Base64
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    return success(data={
        "captcha_id": captcha_id,
        "captcha_image": f"data:image/png;base64,{image_base64}",
        "expires_in": 300  # 5分钟
    })


@router.post("/captcha/verify", summary="验证图形验证码")
async def verify_captcha_endpoint(
    captcha_id: str,
    captcha_code: str
):
    """验证图形验证码（测试用）

    - 正常情况下验证码在登录时一并验证
    - 此接口仅供测试使用
    """
    valid, message = verify_captcha(captcha_id, captcha_code)

    if not valid:
        raise HTTPException(status_code=400, detail=message)

    return success(message=message)
