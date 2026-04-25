"""
PetPal - 管理后台 - 数据统计API

提供数据分析功能：
- 平台概览数据
- 用户增长分析
- 内容数据分析
- 商城销售分析
- 活动数据分析
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, cast, Date

from app.database import get_db
from app.models.user import User
from app.models.pet import Pet
from app.models.content import Post, Comment
from app.models.shop import Order, Product, OrderItem
from app.models.social import Activity, ActivityParticipant, Follow
from app.models.points import PointsRecord
from app.utils.deps import get_current_user
from app.utils.response import success

router = APIRouter()


# ==================== 权限检查 ====================

def require_admin(current_user: User = Depends(get_current_user)):
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# ==================== 平台概览 ====================

@router.get("/overview", summary="平台数据概览")
async def get_platform_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取平台整体数据概览"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    # 用户数据
    total_users = db.query(func.count(User.id)).scalar() or 0
    today_users = db.query(func.count(User.id)).filter(
        User.created_at >= today_start
    ).scalar() or 0
    yesterday_users = db.query(func.count(User.id)).filter(
        User.created_at >= yesterday_start,
        User.created_at < today_start
    ).scalar() or 0

    # 宠物数据
    total_pets = db.query(func.count(Pet.id)).filter(Pet.deleted_at.is_(None)).scalar() or 0
    today_pets = db.query(func.count(Pet.id)).filter(
        Pet.created_at >= today_start,
        Pet.deleted_at.is_(None)
    ).scalar() or 0

    # 内容数据
    total_posts = db.query(func.count(Post.id)).filter(
        Post.deleted_at.is_(None)
    ).scalar() or 0
    today_posts = db.query(func.count(Post.id)).filter(
        Post.created_at >= today_start,
        Post.deleted_at.is_(None)
    ).scalar() or 0

    total_comments = db.query(func.count(Comment.id)).filter(
        Comment.status == 1
    ).scalar() or 0

    # 订单数据
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    today_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= today_start
    ).scalar() or 0

    today_revenue = db.query(func.sum(Order.pay_amount)).filter(
        Order.created_at >= today_start,
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    total_revenue = db.query(func.sum(Order.pay_amount)).filter(
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    # 活动数据
    total_activities = db.query(func.count(Activity.id)).filter(
        Activity.status != "cancelled"
    ).scalar() or 0
    upcoming_activities = db.query(func.count(Activity.id)).filter(
        Activity.status == "upcoming"
    ).scalar() or 0

    # 计算增长率
    def calc_growth(today_val, yesterday_val):
        if yesterday_val == 0:
            return 100 if today_val > 0 else 0
        return round((today_val - yesterday_val) / yesterday_val * 100, 1)

    return success(data={
        "users": {
            "total": total_users,
            "today": today_users,
            "growth": calc_growth(today_users, yesterday_users)
        },
        "pets": {
            "total": total_pets,
            "today": today_pets
        },
        "content": {
            "total_posts": total_posts,
            "today_posts": today_posts,
            "total_comments": total_comments
        },
        "orders": {
            "total": total_orders,
            "today": today_orders,
            "today_revenue": float(today_revenue),
            "total_revenue": float(total_revenue)
        },
        "activities": {
            "total": total_activities,
            "upcoming": upcoming_activities
        }
    })


# ==================== 用户分析 ====================

@router.get("/users/growth", summary="用户增长趋势")
async def get_user_growth(
    days: int = Query(30, ge=7, le=90, description="统计天数"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户增长趋势数据"""
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    # 按天统计新增用户
    daily_stats = db.query(
        cast(User.created_at, Date).label('date'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= start_date
    ).group_by(
        cast(User.created_at, Date)
    ).order_by('date').all()

    stats_dict = {str(s.date): s.count for s in daily_stats}

    result = []
    current_date = start_date
    cumulative = db.query(func.count(User.id)).filter(
        User.created_at < start_date
    ).scalar() or 0

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        daily_count = stats_dict.get(date_str, 0)
        cumulative += daily_count
        result.append({
            "date": date_str,
            "new_users": daily_count,
            "total_users": cumulative
        })
        current_date += timedelta(days=1)

    return success(data=result)


@router.get("/users/active", summary="活跃用户分析")
async def get_active_users(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取活跃用户分析数据"""
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    # 按天统计活跃用户（有登录记录）
    from app.models.login_log import LoginLog

    daily_active = db.query(
        cast(LoginLog.created_at, Date).label('date'),
        func.count(func.distinct(LoginLog.user_id)).label('count')
    ).filter(
        LoginLog.created_at >= start_date,
        LoginLog.status == "success"
    ).group_by(
        cast(LoginLog.created_at, Date)
    ).order_by('date').all()

    stats_dict = {str(s.date): s.count for s in daily_active}

    result = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        result.append({
            "date": date_str,
            "active_users": stats_dict.get(date_str, 0)
        })
        current_date += timedelta(days=1)

    # 计算留存率
    total_users = db.query(func.count(User.id)).scalar() or 1
    week_active = db.query(func.count(func.distinct(LoginLog.user_id))).filter(
        LoginLog.created_at >= end_date - timedelta(days=7),
        LoginLog.status == "success"
    ).scalar() or 0

    return success(data={
        "daily": result,
        "summary": {
            "total_users": total_users,
            "week_active": week_active,
            "active_rate": round(week_active / total_users * 100, 1) if total_users > 0 else 0
        }
    })


@router.get("/users/distribution", summary="用户分布分析")
async def get_user_distribution(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取用户分布数据"""
    # 角色分布
    role_dist = db.query(
        User.role,
        func.count(User.id).label('count')
    ).group_by(User.role).all()

    # 状态分布
    status_dist = db.query(
        User.status,
        func.count(User.id).label('count')
    ).group_by(User.status).all()

    # 性别分布
    gender_dist = db.query(
        User.gender,
        func.count(User.id).label('count')
    ).group_by(User.gender).all()

    # 会员等级分布
    level_dist = db.query(
        User.member_level,
        func.count(User.id).label('count')
    ).group_by(User.member_level).all()

    return success(data={
        "role": {r: c for r, c in role_dist},
        "status": {s: c for s, c in status_dist},
        "gender": {g or "unknown": c for g, c in gender_dist},
        "member_level": {l: c for l, c in level_dist}
    })


# ==================== 内容分析 ====================

@router.get("/content/overview", summary="内容数据概览")
async def get_content_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取内容数据概览"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # 帖子统计
    total_posts = db.query(func.count(Post.id)).filter(
        Post.deleted_at.is_(None)
    ).scalar() or 0

    week_posts = db.query(func.count(Post.id)).filter(
        Post.created_at >= week_start,
        Post.deleted_at.is_(None)
    ).scalar() or 0

    # 帖子状态分布
    post_status = db.query(
        Post.status,
        func.count(Post.id).label('count')
    ).filter(Post.deleted_at.is_(None)).group_by(Post.status).all()

    # 帖子类型分布
    post_types = db.query(
        Post.content_type,
        func.count(Post.id).label('count')
    ).filter(Post.deleted_at.is_(None)).group_by(Post.content_type).all()

    # 评论统计
    total_comments = db.query(func.count(Comment.id)).filter(
        Comment.status == 1
    ).scalar() or 0

    week_comments = db.query(func.count(Comment.id)).filter(
        Comment.created_at >= week_start,
        Comment.status == 1
    ).scalar() or 0

    # 互动数据
    total_views = db.query(func.sum(Post.views_count)).scalar() or 0
    total_likes = db.query(func.sum(Post.likes_count)).scalar() or 0
    total_shares = db.query(func.sum(Post.shares_count)).scalar() or 0

    return success(data={
        "posts": {
            "total": total_posts,
            "week_new": week_posts,
            "status_distribution": {s: c for s, c in post_status},
            "type_distribution": {t or "text": c for t, c in post_types}
        },
        "comments": {
            "total": total_comments,
            "week_new": week_comments
        },
        "interactions": {
            "total_views": int(total_views),
            "total_likes": int(total_likes),
            "total_shares": int(total_shares)
        }
    })


@router.get("/content/trend", summary="内容发布趋势")
async def get_content_trend(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取内容发布趋势"""
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    # 帖子发布趋势
    post_stats = db.query(
        cast(Post.created_at, Date).label('date'),
        func.count(Post.id).label('count')
    ).filter(
        Post.created_at >= start_date,
        Post.deleted_at.is_(None)
    ).group_by(
        cast(Post.created_at, Date)
    ).order_by('date').all()

    # 评论趋势
    comment_stats = db.query(
        cast(Comment.created_at, Date).label('date'),
        func.count(Comment.id).label('count')
    ).filter(
        Comment.created_at >= start_date,
        Comment.status == 1
    ).group_by(
        cast(Comment.created_at, Date)
    ).order_by('date').all()

    post_dict = {str(s.date): s.count for s in post_stats}
    comment_dict = {str(s.date): s.count for s in comment_stats}

    result = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        result.append({
            "date": date_str,
            "posts": post_dict.get(date_str, 0),
            "comments": comment_dict.get(date_str, 0)
        })
        current_date += timedelta(days=1)

    return success(data=result)


@router.get("/content/top", summary="热门内容排行")
async def get_top_content(
    metric: str = Query("views", description="排序指标: views/likes/comments"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取热门内容排行"""
    query = db.query(Post).filter(
        Post.deleted_at.is_(None),
        Post.status == 1
    )

    if metric == "likes":
        query = query.order_by(desc(Post.likes_count))
    elif metric == "comments":
        query = query.order_by(desc(Post.comments_count))
    else:  # views
        query = query.order_by(desc(Post.views_count))

    posts = query.limit(limit).all()

    # 获取作者信息
    author_ids = [p.author_id for p in posts]
    authors = db.query(User).filter(User.id.in_(author_ids)).all() if author_ids else []
    author_map = {a.id: a for a in authors}

    result = []
    for post in posts:
        author = author_map.get(post.author_id)
        result.append({
            "id": post.id,
            "title": post.title,
            "content_type": post.content_type,
            "views_count": post.views_count,
            "likes_count": post.likes_count,
            "comments_count": post.comments_count,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "author": {
                "id": author.id,
                "nickname": author.nickname
            } if author else None
        })

    return success(data=result)


# ==================== 商城分析 ====================

@router.get("/shop/overview", summary="商城数据概览")
async def get_shop_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取商城数据概览"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    month_start = today_start - timedelta(days=30)

    # 订单统计
    total_orders = db.query(func.count(Order.id)).scalar() or 0
    today_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= today_start
    ).scalar() or 0
    week_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= week_start
    ).scalar() or 0

    # 销售额
    total_revenue = db.query(func.sum(Order.pay_amount)).filter(
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    today_revenue = db.query(func.sum(Order.pay_amount)).filter(
        Order.created_at >= today_start,
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    week_revenue = db.query(func.sum(Order.pay_amount)).filter(
        Order.created_at >= week_start,
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    month_revenue = db.query(func.sum(Order.pay_amount)).filter(
        Order.created_at >= month_start,
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    # 订单状态分布
    order_status = db.query(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status).all()

    # 商品统计
    total_products = db.query(func.count(Product.id)).filter(
        Product.deleted_at.is_(None)
    ).scalar() or 0

    active_products = db.query(func.count(Product.id)).filter(
        Product.deleted_at.is_(None),
        Product.status == 1
    ).scalar() or 0

    # 平均客单价
    avg_order_amount = db.query(func.avg(Order.pay_amount)).filter(
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    return success(data={
        "orders": {
            "total": total_orders,
            "today": today_orders,
            "week": week_orders,
            "status_distribution": {s: c for s, c in order_status}
        },
        "revenue": {
            "total": float(total_revenue),
            "today": float(today_revenue),
            "week": float(week_revenue),
            "month": float(month_revenue),
            "avg_order_amount": round(float(avg_order_amount), 2)
        },
        "products": {
            "total": total_products,
            "active": active_products
        }
    })


@router.get("/shop/sales-trend", summary="销售趋势")
async def get_sales_trend(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取销售趋势数据"""
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    # 订单数趋势
    order_stats = db.query(
        cast(Order.created_at, Date).label('date'),
        func.count(Order.id).label('orders'),
        func.sum(Order.pay_amount).label('revenue')
    ).filter(
        Order.created_at >= start_date,
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).group_by(
        cast(Order.created_at, Date)
    ).order_by('date').all()

    stats_dict = {str(s.date): {"orders": s.orders, "revenue": float(s.revenue or 0)} for s in order_stats}

    result = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        data = stats_dict.get(date_str, {"orders": 0, "revenue": 0})
        result.append({
            "date": date_str,
            "orders": data["orders"],
            "revenue": data["revenue"]
        })
        current_date += timedelta(days=1)

    return success(data=result)


@router.get("/shop/top-products", summary="热销商品排行")
async def get_top_products(
    metric: str = Query("sales", description="排序指标: sales销量 revenue销售额"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取热销商品排行"""
    query = db.query(
        Product.id,
        Product.name,
        Product.cover_image,
        Product.price,
        func.sum(OrderItem.quantity).label('total_sales'),
        func.sum(OrderItem.total_price).label('total_revenue')
    ).join(
        OrderItem, OrderItem.product_id == Product.id
    ).join(
        Order, Order.id == OrderItem.order_id
    ).filter(
        Order.status.in_(["paid", "shipped", "received", "completed"]),
        Product.deleted_at.is_(None)
    ).group_by(Product.id)

    if metric == "revenue":
        query = query.order_by(desc('total_revenue'))
    else:  # sales
        query = query.order_by(desc('total_sales'))

    products = query.limit(limit).all()

    result = [{
        "id": p.id,
        "name": p.name,
        "cover_image": p.cover_image,
        "price": float(p.price),
        "total_sales": int(p.total_sales or 0),
        "total_revenue": float(p.total_revenue or 0)
    } for p in products]

    return success(data=result)


# ==================== 活动分析 ====================

@router.get("/activities/overview", summary="活动数据概览")
async def get_activities_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取活动数据概览"""
    now = datetime.now()
    month_start = now - timedelta(days=30)

    # 活动统计
    total_activities = db.query(func.count(Activity.id)).filter(
        Activity.status != "cancelled"
    ).scalar() or 0

    status_dist = db.query(
        Activity.status,
        func.count(Activity.id).label('count')
    ).group_by(Activity.status).all()

    type_dist = db.query(
        Activity.activity_type,
        func.count(Activity.id).label('count')
    ).filter(Activity.status != "cancelled").group_by(Activity.activity_type).all()

    # 参与统计
    total_participants = db.query(func.count(ActivityParticipant.id)).filter(
        ActivityParticipant.status != "cancelled"
    ).scalar() or 0

    total_checkins = db.query(func.count(ActivityParticipant.id)).filter(
        ActivityParticipant.status == "checked_in"
    ).scalar() or 0

    # 本月活动
    month_activities = db.query(func.count(Activity.id)).filter(
        Activity.created_at >= month_start,
        Activity.status != "cancelled"
    ).scalar() or 0

    return success(data={
        "activities": {
            "total": total_activities,
            "month_new": month_activities,
            "status_distribution": {s: c for s, c in status_dist},
            "type_distribution": {t: c for t, c in type_dist}
        },
        "participation": {
            "total_participants": total_participants,
            "total_checkins": total_checkins,
            "checkin_rate": round(total_checkins / total_participants * 100, 1) if total_participants > 0 else 0
        }
    })


@router.get("/activities/trend", summary="活动趋势")
async def get_activities_trend(
    days: int = Query(30, ge=7, le=90),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取活动趋势数据"""
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=days)

    # 活动创建趋势
    activity_stats = db.query(
        cast(Activity.created_at, Date).label('date'),
        func.count(Activity.id).label('count')
    ).filter(
        Activity.created_at >= start_date,
        Activity.status != "cancelled"
    ).group_by(
        cast(Activity.created_at, Date)
    ).order_by('date').all()

    # 报名趋势
    join_stats = db.query(
        cast(ActivityParticipant.created_at, Date).label('date'),
        func.count(ActivityParticipant.id).label('count')
    ).filter(
        ActivityParticipant.created_at >= start_date,
        ActivityParticipant.status != "cancelled"
    ).group_by(
        cast(ActivityParticipant.created_at, Date)
    ).order_by('date').all()

    activity_dict = {str(s.date): s.count for s in activity_stats}
    join_dict = {str(s.date): s.count for s in join_stats}

    result = []
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        result.append({
            "date": date_str,
            "activities": activity_dict.get(date_str, 0),
            "participants": join_dict.get(date_str, 0)
        })
        current_date += timedelta(days=1)

    return success(data=result)


# ==================== 积分分析 ====================

@router.get("/points/overview", summary="积分数据概览")
async def get_points_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取积分数据概览"""
    # 总积分（用户持有）
    total_points = db.query(func.sum(User.points)).scalar() or 0

    # 积分发放统计
    total_issued = db.query(func.sum(PointsRecord.points)).filter(
        PointsRecord.points > 0
    ).scalar() or 0

    # 积分消费统计
    total_consumed = db.query(func.sum(func.abs(PointsRecord.points))).filter(
        PointsRecord.points < 0
    ).scalar() or 0

    # 按来源统计
    source_stats = db.query(
        PointsRecord.source_type,
        func.sum(PointsRecord.points).label('total')
    ).filter(
        PointsRecord.points > 0
    ).group_by(PointsRecord.source_type).all()

    return success(data={
        "total_points": int(total_points),
        "total_issued": int(total_issued),
        "total_consumed": int(total_consumed),
        "source_distribution": {s: int(t) for s, t in source_stats}
    })


# ==================== 实时数据 ====================

@router.get("/realtime", summary="实时数据")
async def get_realtime_data(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取实时数据（最近1小时）"""
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)

    # 最近1小时新用户
    new_users = db.query(func.count(User.id)).filter(
        User.created_at >= hour_ago
    ).scalar() or 0

    # 最近1小时新帖子
    new_posts = db.query(func.count(Post.id)).filter(
        Post.created_at >= hour_ago,
        Post.deleted_at.is_(None)
    ).scalar() or 0

    # 最近1小时新订单
    new_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= hour_ago
    ).scalar() or 0

    # 最近1小时销售额
    hour_revenue = db.query(func.sum(Order.pay_amount)).filter(
        Order.created_at >= hour_ago,
        Order.status.in_(["paid", "shipped", "received", "completed"])
    ).scalar() or 0

    # 在线用户估算（5分钟内有登录记录）
    from app.models.login_log import LoginLog
    five_min_ago = now - timedelta(minutes=5)
    online_estimate = db.query(func.count(func.distinct(LoginLog.user_id))).filter(
        LoginLog.created_at >= five_min_ago,
        LoginLog.status == "success"
    ).scalar() or 0

    return success(data={
        "timestamp": now.isoformat(),
        "last_hour": {
            "new_users": new_users,
            "new_posts": new_posts,
            "new_orders": new_orders,
            "revenue": float(hour_revenue)
        },
        "online_estimate": online_estimate
    })
