"""
PetPal - 管理后台 - 内容审核API

提供内容管理功能：
- 帖子审核
- 评论审核
- 举报处理
- 反馈处理
- 内容统计
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.content import Post, Comment
from app.models.user_settings import UserFeedback, UserReport
from app.models.social import Notification
from app.utils.deps import get_current_user
from app.utils.response import success, page_response

router = APIRouter()


# ==================== 权限检查 ====================

def require_admin(current_user: User = Depends(get_current_user)):
    """要求管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


# ==================== Schema定义 ====================

class ReviewPostRequest(BaseModel):
    """审核帖子"""
    action: str = Field(..., pattern="^(approve|reject|delete)$")
    reason: Optional[str] = Field(None, max_length=500)


class ReviewCommentRequest(BaseModel):
    """审核评论"""
    action: str = Field(..., pattern="^(approve|delete)$")
    reason: Optional[str] = Field(None, max_length=500)


class HandleReportRequest(BaseModel):
    """处理举报"""
    action: str = Field(..., pattern="^(valid|invalid|delete_content)$")
    result: Optional[str] = Field(None, max_length=500)
    punish_user: bool = False
    punish_days: int = Field(0, ge=0, le=365)


class HandleFeedbackRequest(BaseModel):
    """处理反馈"""
    status: str = Field(..., pattern="^(processing|resolved|closed)$")
    reply: Optional[str] = Field(None, max_length=1000)


# ==================== 帖子审核 ====================

@router.get("/posts", summary="获取帖子列表")
async def get_posts(
    status: Optional[int] = Query(None, description="状态: 0审核中 1已发布 2已下架 3已删除"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    author_id: Optional[int] = Query(None, description="作者ID"),
    is_reported: Optional[bool] = Query(None, description="是否被举报"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取帖子列表（管理）"""
    query = db.query(Post)

    if status is not None:
        query = query.filter(Post.status == status)

    if keyword:
        keyword_filter = f"%{keyword}%"
        query = query.filter(
            or_(
                Post.title.ilike(keyword_filter),
                Post.content.ilike(keyword_filter)
            )
        )

    if author_id:
        query = query.filter(Post.author_id == author_id)

    if is_reported:
        # 获取被举报的帖子ID
        reported_ids = db.query(UserReport.target_id).filter(
            UserReport.target_type == "post",
            UserReport.status == "pending"
        ).subquery()
        query = query.filter(Post.id.in_(reported_ids))

    if start_time:
        query = query.filter(Post.created_at >= start_time)
    if end_time:
        query = query.filter(Post.created_at <= end_time)

    query = query.order_by(desc(Post.created_at))

    total = query.count()
    posts = query.offset((page - 1) * page_size).limit(page_size).all()

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
            "content": post.content[:200] if post.content else None,
            "content_type": post.content_type,
            "cover_url": post.cover_url,
            "status": post.status,
            "views_count": post.views_count,
            "likes_count": post.likes_count,
            "comments_count": post.comments_count,
            "is_top": bool(post.is_top),
            "is_hot": bool(post.is_hot),
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "author": {
                "id": author.id,
                "nickname": author.nickname,
                "avatar_url": author.avatar_url
            } if author else None
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.get("/posts/{post_id}", summary="获取帖子详情")
async def get_post_detail(
    post_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取帖子详情（管理）"""
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    author = db.query(User).filter(User.id == post.author_id).first()

    import json
    post_dict = {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "content_type": post.content_type,
        "media_urls": json.loads(post.media_urls) if post.media_urls else [],
        "cover_url": post.cover_url,
        "tags": json.loads(post.tags) if post.tags else [],
        "topics": json.loads(post.topics) if post.topics else [],
        "location": post.location,
        "status": post.status,
        "views_count": post.views_count,
        "likes_count": post.likes_count,
        "comments_count": post.comments_count,
        "shares_count": post.shares_count,
        "collects_count": post.collects_count,
        "is_top": bool(post.is_top),
        "is_hot": bool(post.is_hot),
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "deleted_at": post.deleted_at.isoformat() if post.deleted_at else None,
        "author": {
            "id": author.id,
            "nickname": author.nickname,
            "avatar_url": author.avatar_url,
            "status": author.status
        } if author else None
    }

    # 获取相关举报
    reports = db.query(UserReport).filter(
        UserReport.target_type == "post",
        UserReport.target_id == post_id
    ).order_by(desc(UserReport.created_at)).all()

    post_dict["reports"] = [r.to_dict() for r in reports]

    return success(data=post_dict)


@router.put("/posts/{post_id}/review", summary="审核帖子")
async def review_post(
    post_id: int,
    request: ReviewPostRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """审核帖子"""
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    old_status = post.status

    if request.action == "approve":
        post.status = 1
        message = "帖子已通过审核"
    elif request.action == "reject":
        post.status = 2
        message = "帖子已下架"
    else:  # delete
        post.status = 3
        post.deleted_at = datetime.now()
        message = "帖子已删除"

    # 通知作者
    if request.action in ["reject", "delete"]:
        notification = Notification(
            user_id=post.author_id,
            notify_type="system",
            target_type="post",
            target_id=post_id,
            title="内容审核通知",
            content=f"您的帖子「{post.title or '无标题'}」{message}。原因：{request.reason or '违反社区规范'}"
        )
        db.add(notification)

    # 记录审计日志
    from app.models.audit_log import AuditLog
    audit_log = AuditLog(
        user_id=current_user.id,
        action=f"review_post_{request.action}",
        resource_type="post",
        resource_id=post_id,
        old_value=str(old_status),
        new_value=str(post.status),
        reason=request.reason,
        ip_address=""
    )
    db.add(audit_log)

    db.commit()

    return success(message=message)


@router.put("/posts/{post_id}/top", summary="置顶/取消置顶")
async def toggle_post_top(
    post_id: int,
    is_top: bool = Body(..., embed=True),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """置顶/取消置顶帖子"""
    post = db.query(Post).filter(Post.id == post_id, Post.status == 1).first()

    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    post.is_top = 1 if is_top else 0
    db.commit()

    return success(message="置顶" if is_top else "取消置顶")


@router.put("/posts/{post_id}/hot", summary="设为热门/取消热门")
async def toggle_post_hot(
    post_id: int,
    is_hot: bool = Body(..., embed=True),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """设为热门/取消热门"""
    post = db.query(Post).filter(Post.id == post_id, Post.status == 1).first()

    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")

    post.is_hot = 1 if is_hot else 0
    db.commit()

    return success(message="设为热门" if is_hot else "取消热门")


# ==================== 评论审核 ====================

@router.get("/comments", summary="获取评论列表")
async def get_comments(
    status: Optional[int] = Query(None, description="状态: 0审核中 1正常 2已删除"),
    post_id: Optional[int] = Query(None, description="帖子ID"),
    user_id: Optional[int] = Query(None, description="用户ID"),
    is_reported: Optional[bool] = Query(None, description="是否被举报"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取评论列表（管理）"""
    query = db.query(Comment)

    if status is not None:
        query = query.filter(Comment.status == status)

    if post_id:
        query = query.filter(Comment.post_id == post_id)

    if user_id:
        query = query.filter(Comment.user_id == user_id)

    if is_reported:
        reported_ids = db.query(UserReport.target_id).filter(
            UserReport.target_type == "comment",
            UserReport.status == "pending"
        ).subquery()
        query = query.filter(Comment.id.in_(reported_ids))

    query = query.order_by(desc(Comment.created_at))

    total = query.count()
    comments = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取用户信息
    user_ids = [c.user_id for c in comments]
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u for u in users}

    result = []
    for comment in comments:
        user = user_map.get(comment.user_id)
        result.append({
            "id": comment.id,
            "post_id": comment.post_id,
            "content": comment.content,
            "image_url": comment.image_url,
            "status": comment.status,
            "likes_count": comment.likes_count,
            "replies_count": comment.replies_count,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "user": {
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url
            } if user else None
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.put("/comments/{comment_id}/review", summary="审核评论")
async def review_comment(
    comment_id: int,
    request: ReviewCommentRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """审核评论"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()

    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    if request.action == "approve":
        comment.status = 1
        message = "评论已通过"
    else:  # delete
        comment.status = 2
        message = "评论已删除"

        # 更新帖子评论数
        post = db.query(Post).filter(Post.id == comment.post_id).first()
        if post:
            post.comments_count = max(0, post.comments_count - 1)

        # 通知用户
        notification = Notification(
            user_id=comment.user_id,
            notify_type="system",
            target_type="comment",
            target_id=comment_id,
            title="评论审核通知",
            content=f"您的评论已被删除。原因：{request.reason or '违反社区规范'}"
        )
        db.add(notification)

    db.commit()

    return success(message=message)


# ==================== 举报处理 ====================

@router.get("/reports", summary="获取举报列表")
async def get_reports(
    target_type: Optional[str] = Query(None, description="举报类型: user/post/comment"),
    status: Optional[str] = Query(None, description="状态: pending/processing/valid/invalid"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取举报列表"""
    query = db.query(UserReport)

    if target_type:
        query = query.filter(UserReport.target_type == target_type)

    if status:
        query = query.filter(UserReport.status == status)

    query = query.order_by(desc(UserReport.created_at))

    total = query.count()
    reports = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取举报人信息
    reporter_ids = [r.reporter_id for r in reports if r.reporter_id]
    reporters = db.query(User).filter(User.id.in_(reporter_ids)).all() if reporter_ids else []
    reporter_map = {u.id: u for u in reporters}

    result = []
    for report in reports:
        reporter = reporter_map.get(report.reporter_id) if report.reporter_id else None
        result.append({
            "id": report.id,
            "target_type": report.target_type,
            "target_id": report.target_id,
            "reason": report.reason,
            "description": report.description,
            "status": report.status,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "reporter": {
                "id": reporter.id,
                "nickname": reporter.nickname
            } if reporter else None
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.put("/reports/{report_id}", summary="处理举报")
async def handle_report(
    report_id: int,
    request: HandleReportRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """处理举报"""
    report = db.query(UserReport).filter(UserReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="举报不存在")

    if request.action == "valid":
        report.status = "valid"
    elif request.action == "invalid":
        report.status = "invalid"
    else:  # delete_content
        report.status = "valid"
        # 删除被举报的内容
        if report.target_type == "post":
            post = db.query(Post).filter(Post.id == report.target_id).first()
            if post:
                post.status = 3
                post.deleted_at = datetime.now()
        elif report.target_type == "comment":
            comment = db.query(Comment).filter(Comment.id == report.target_id).first()
            if comment:
                comment.status = 2

    report.handle_result = request.result
    report.handled_at = datetime.now()

    # 处罚用户
    if request.punish_user and request.punish_days > 0:
        # 获取被举报内容的作者
        target_user_id = None
        if report.target_type == "post":
            post = db.query(Post).filter(Post.id == report.target_id).first()
            if post:
                target_user_id = post.author_id
        elif report.target_type == "comment":
            comment = db.query(Comment).filter(Comment.id == report.target_id).first()
            if comment:
                target_user_id = comment.user_id
        elif report.target_type == "user":
            target_user_id = report.target_id

        if target_user_id:
            target_user = db.query(User).filter(User.id == target_user_id).first()
            if target_user and target_user.role != "admin":
                target_user.status = 2  # 限制状态

    db.commit()

    return success(message="举报已处理")


# ==================== 反馈处理 ====================

@router.get("/feedbacks", summary="获取反馈列表")
async def get_feedbacks(
    feedback_type: Optional[str] = Query(None, description="反馈类型"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取反馈列表"""
    query = db.query(UserFeedback)

    if feedback_type:
        query = query.filter(UserFeedback.feedback_type == feedback_type)

    if status:
        query = query.filter(UserFeedback.status == status)

    query = query.order_by(desc(UserFeedback.created_at))

    total = query.count()
    feedbacks = query.offset((page - 1) * page_size).limit(page_size).all()

    # 获取用户信息
    user_ids = [f.user_id for f in feedbacks if f.user_id]
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u for u in users}

    result = []
    for feedback in feedbacks:
        user = user_map.get(feedback.user_id) if feedback.user_id else None
        result.append({
            "id": feedback.id,
            "feedback_type": feedback.feedback_type,
            "content": feedback.content,
            "contact": feedback.contact,
            "status": feedback.status,
            "reply": feedback.reply,
            "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            "user": {
                "id": user.id,
                "nickname": user.nickname
            } if user else None
        })

    return page_response(data=result, page=page, page_size=page_size, total=total)


@router.put("/feedbacks/{feedback_id}", summary="处理反馈")
async def handle_feedback(
    feedback_id: int,
    request: HandleFeedbackRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """处理反馈"""
    feedback = db.query(UserFeedback).filter(UserFeedback.id == feedback_id).first()

    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")

    feedback.status = request.status
    if request.reply:
        feedback.reply = request.reply
        feedback.replied_at = datetime.now()

        # 通知用户
        if feedback.user_id:
            notification = Notification(
                user_id=feedback.user_id,
                notify_type="system",
                title="反馈回复通知",
                content=f"您的反馈已收到回复：{request.reply[:100]}..."
            )
            db.add(notification)

    db.commit()

    return success(message="反馈已处理")


# ==================== 内容统计 ====================

@router.get("/stats", summary="内容统计")
async def get_content_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """获取内容统计数据"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 帖子统计
    total_posts = db.query(func.count(Post.id)).filter(Post.deleted_at.is_(None)).scalar() or 0
    today_posts = db.query(func.count(Post.id)).filter(
        Post.created_at >= today_start,
        Post.deleted_at.is_(None)
    ).scalar() or 0
    pending_posts = db.query(func.count(Post.id)).filter(Post.status == 0).scalar() or 0

    # 评论统计
    total_comments = db.query(func.count(Comment.id)).filter(Comment.status == 1).scalar() or 0
    today_comments = db.query(func.count(Comment.id)).filter(
        Comment.created_at >= today_start,
        Comment.status == 1
    ).scalar() or 0

    # 举报统计
    pending_reports = db.query(func.count(UserReport.id)).filter(
        UserReport.status == "pending"
    ).scalar() or 0

    # 反馈统计
    pending_feedbacks = db.query(func.count(UserFeedback.id)).filter(
        UserFeedback.status == "pending"
    ).scalar() or 0

    return success(data={
        "posts": {
            "total": total_posts,
            "today": today_posts,
            "pending": pending_posts
        },
        "comments": {
            "total": total_comments,
            "today": today_comments
        },
        "reports": {
            "pending": pending_reports
        },
        "feedbacks": {
            "pending": pending_feedbacks
        }
    })
