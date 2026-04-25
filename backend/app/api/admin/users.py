"""
PetPal - 管理后台 - 用户管理API

提供用户管理功能：
- 用户列表与搜索
- 用户详情
- 用户状态管理（禁用/启用）
- 用户角色管理
- 用户数据统计
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Body, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.content import Post, Comment
from app.models.shop import Order
from app.models.social import Follow
from app.models.login_log import LoginLog
from app.utils.deps import get_current_user
from app.utils.response import success, page_response
from app.utils.data_masking import mask_phone, mask_email

router = APIRouter()


def get_client_ip(request: Request) -> str:
    """获取客户端真实IP地址"""
    # 优先从 X-Forwarded-For 头获取（反向代理场景）
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # 其次从 X-Real-IP 头获取
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    # 最后使用直连IP
    return request.client.host if request.client else ""


# ==================== 权限检查 ====================

def require_admin(current_user: User = Depends(get_current_user)):
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# ==================== Schema定义 ====================

class UpdateUserStatusRequest(BaseModel):
    """更新用户状态"""
    status: int = Field(..., ge=0, le=2, description="状态: 0禁用 1正常 2限制")
    reason: Optional[str] = Field(None, max_length=500)


class UpdateUserRoleRequest(BaseModel):
    """更新用户角色"""
    role: str = Field(..., pattern="^(user|creator|expert|admin)$")


class BatchUserActionRequest(BaseModel):
    """批量用户操作"""
    user_ids: List[int] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern="^(disable|enable|delete)$")
    reason: Optional[str] = None


# ==================== 用户列表 ====================

@router.get("", summary="获取用户列表")
async def get_users(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    role: Optional[str] = Query(None, description="角色筛选"),
    status: Optional[int] = Query(None, description="状态筛选"),
    register_start: Optional[datetime] = Query(None, description="注册开始时间"),
    register_end: Optional[datetime] = Query(None, description="注册结束时间"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户列表"""
    query = db.query(User)

    # 关键词搜索
    if keyword:
        keyword_filter = f"%{keyword}%"
        query = query.filter(
            or_(
                User.nickname.ilike(keyword_filter),
                User.phone.ilike(keyword_filter),
                User.email.ilike(keyword_filter),
                User.id == keyword if keyword.isdigit() else False
            )
        )

    # 角色筛选
    if role:
        query = query.filter(User.role == role)

    # 状态筛选
    if status is not None:
        query = query.filter(User.status == status)

    # 时间筛选
    if register_start:
        query = query.filter(User.created_at >= register_start)
    if register_end:
        query = query.filter(User.created_at <= register_end)

    # 排序
    sort_column = getattr(User, sort_by, User.created_at)
    if sort_order == "asc":
        query = query.order_by(sort_column)
    else:
        query = query.order_by(desc(sort_column))

    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for user in users:
        result.append({
            "id": user.id,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "phone": mask_phone(user.phone),
            "email": mask_email(user.email),
            "role": user.role,
            "status": user.status,
            "points": user.points,
            "member_level": user.member_level,
            "posts_count": user.posts_count,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/{user_id}", summary="获取用户详情")
async def get_user_detail(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户详细信息"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 基本信息
    user_dict = {
        "id": user.id,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "phone": mask_phone(user.phone),
        "email": mask_email(user.email),
        "gender": user.gender,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "bio": user.bio,
        "role": user.role,
        "status": user.status,
        "points": user.points,
        "member_level": user.member_level,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None
    }

    # 统计信息
    pets_count = db.query(func.count(Pet.id)).filter(
        Pet.owner_id == user_id,
        Pet.deleted_at.is_(None)
    ).scalar() or 0

    posts_count = db.query(func.count(Post.id)).filter(
        Post.author_id == user_id,
        Post.deleted_at.is_(None)
    ).scalar() or 0

    comments_count = db.query(func.count(Comment.id)).filter(
        Comment.user_id == user_id,
        Comment.status == 1
    ).scalar() or 0

    orders_count = db.query(func.count(Order.id)).filter(
        Order.user_id == user_id
    ).scalar() or 0

    total_spent = db.query(func.sum(Order.pay_amount)).filter(
        Order.user_id == user_id,
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    user_dict["statistics"] = {
        "pets_count": pets_count,
        "posts_count": posts_count,
        "comments_count": comments_count,
        "orders_count": orders_count,
        "total_spent": float(total_spent),
        "followers_count": user.followers_count,
        "following_count": user.following_count,
        "likes_count": user.likes_count
    }

    # 最近登录记录
    recent_logins = db.query(LoginLog).filter(
        LoginLog.user_id == user_id
    ).order_by(desc(LoginLog.created_at)).limit(5).all()

    user_dict["recent_logins"] = [{
        "ip": log.ip_address,
        "device": log.device_type,
        "time": log.created_at.isoformat() if log.created_at else None,
        "status": log.status
    } for log in recent_logins]

    return success(data=user_dict)


# ==================== 用户状态管理 ====================

@router.put("/{user_id}/status", summary="更新用户状态")
async def update_user_status(
    user_id: int,
    req: Request,
    body: UpdateUserStatusRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """更新用户状态（禁用/启用）"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.role == "admin" and user.id != current_user.id:
        raise HTTPException(status_code=403, detail="无法修改其他管理员状态")

    old_status = user.status
    user.status = body.status

    # 记录审计日志
    from app.models.audit_log import AuditLog
    audit_log = AuditLog(
        user_id=current_user.id,
        action="update_status",
        resource_type="user",
        resource_id=user_id,
        old_value=str(old_status),
        new_value=str(body.status),
        reason=body.reason,
        ip_address=get_client_ip(req)
    )
    db.add(audit_log)

    db.commit()

    status_text = {0: "禁用", 1: "正常", 2: "限制"}
    return success(message=f"用户状态已更新为{status_text.get(body.status, '未知')}")


@router.put("/{user_id}/role", summary="更新用户角色")
async def update_user_role(
    user_id: int,
    req: Request,
    body: UpdateUserRoleRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """更新用户角色"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="无法修改自己的角色")

    old_role = user.role
    user.role = body.role

    # 记录审计日志
    from app.models.audit_log import AuditLog
    audit_log = AuditLog(
        user_id=current_user.id,
        action="update_role",
        resource_type="user",
        resource_id=user_id,
        old_value=old_role,
        new_value=body.role,
        ip_address=get_client_ip(req)
    )
    db.add(audit_log)

    db.commit()

    return success(message=f"用户角色已更新为{body.role}")


@router.post("/batch", summary="批量操作用户")
async def batch_user_action(
    request: BatchUserActionRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """批量操作用户"""
    users = db.query(User).filter(
        User.id.in_(request.user_ids),
        User.role != "admin"  # 不能批量操作管理员
    ).all()

    if not users:
        raise HTTPException(status_code=400, detail="未找到可操作的用户")

    affected = 0
    for user in users:
        if request.action == "disable":
            user.status = 0
            affected += 1
        elif request.action == "enable":
            user.status = 1
            affected += 1
        elif request.action == "delete":
            # 软删除（实际项目可能需要更复杂的处理）
            user.status = 0
            user.nickname = f"已注销用户{user.id}"
            affected += 1

    db.commit()

    return success(message=f"已处理{affected}个用户")


# ==================== 用户统计 ====================

@router.get("/stats/overview", summary="用户统计概览")
async def get_user_stats_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户统计概览"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    # 总用户数
    total_users = db.query(func.count(User.id)).scalar() or 0

    # 今日新增
    today_new = db.query(func.count(User.id)).filter(
        User.created_at >= today_start
    ).scalar() or 0

    # 本周新增
    week_new = db.query(func.count(User.id)).filter(
        User.created_at >= week_start
    ).scalar() or 0

    # 本月新增
    month_new = db.query(func.count(User.id)).filter(
        User.created_at >= month_start
    ).scalar() or 0

    # 活跃用户（7天内登录）
    active_users = db.query(func.count(User.id)).filter(
        User.last_login >= week_start
    ).scalar() or 0

    # 角色分布
    role_distribution = db.query(
        User.role,
        func.count(User.id)
    ).group_by(User.role).all()

    # 状态分布
    status_distribution = db.query(
        User.status,
        func.count(User.id)
    ).group_by(User.status).all()

    return success(data={
        "total_users": total_users,
        "today_new": today_new,
        "week_new": week_new,
        "month_new": month_new,
        "active_users": active_users,
        "active_rate": round(active_users / total_users * 100, 1) if total_users > 0 else 0,
        "role_distribution": {r: c for r, c in role_distribution},
        "status_distribution": {s: c for s, c in status_distribution}
    })


@router.get("/stats/trend", summary="用户增长趋势")
async def get_user_trend(
    days: int = Query(30, ge=7, le=90, description="统计天数"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户增长趋势"""
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    # 按天统计新增用户
    from sqlalchemy import cast, Date

    daily_stats = db.query(
        cast(User.created_at, Date).label('date'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= start_date
    ).group_by(
        cast(User.created_at, Date)
    ).order_by('date').all()

    result = []
    current_date = start_date
    stats_dict = {str(s.date): s.count for s in daily_stats}

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        result.append({
            "date": date_str,
            "count": stats_dict.get(date_str, 0)
        })
        current_date += timedelta(days=1)

    return success(data=result)
