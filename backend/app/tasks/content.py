"""
PetPal - 内容相关定时任务

- 热门内容更新
- 内容清理
- 活动状态更新
- 话题热度计算
"""
from datetime import datetime, timedelta
from celery import shared_task
from loguru import logger


@shared_task(bind=True, max_retries=3)
def update_hot_posts(self):
    """
    更新热门帖子

    根据浏览量、点赞数、评论数计算热度分数
    """
    from app.database import SessionLocal
    from app.models.content import Post
    from sqlalchemy import desc

    db = SessionLocal()
    try:
        # 计算热度时间窗口（最近7天）
        hot_window = datetime.now() - timedelta(days=7)

        # 获取最近7天的帖子
        posts = db.query(Post).filter(
            Post.status == 1,
            Post.deleted_at.is_(None),
            Post.created_at >= hot_window
        ).all()

        for post in posts:
            # 热度公式：views * 1 + likes * 3 + comments * 5 + shares * 2
            # 时间衰减：越新的帖子权重越高
            hours_old = (datetime.now() - post.created_at).total_seconds() / 3600
            time_decay = max(0.1, 1 - (hours_old / 168))  # 7天内线性衰减

            hot_score = (
                (post.views_count or 0) * 1 +
                (post.likes_count or 0) * 3 +
                (post.comments_count or 0) * 5 +
                (post.shares_count or 0) * 2
            ) * time_decay

            # 更新热门标记
            post.is_hot = 1 if hot_score > 100 else 0

        db.commit()
        logger.info(f"[Celery] 热门帖子更新完成，处理 {len(posts)} 个帖子")
        return {"processed_count": len(posts)}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 热门帖子更新失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def cleanup_deleted_content(self):
    """
    清理已删除的内容

    物理删除30天前软删除的内容
    """
    from app.database import SessionLocal
    from app.models.content import Post, Comment

    db = SessionLocal()
    try:
        cleanup_threshold = datetime.now() - timedelta(days=30)

        # 清理已删除的帖子
        deleted_posts = db.query(Post).filter(
            Post.deleted_at.isnot(None),
            Post.deleted_at <= cleanup_threshold
        ).all()

        post_count = len(deleted_posts)
        for post in deleted_posts:
            # 删除关联的评论
            db.query(Comment).filter(Comment.post_id == post.id).delete()
            db.delete(post)

        # 清理已删除的评论
        deleted_comments = db.query(Comment).filter(
            Comment.status == 2,  # 已删除状态
            Comment.updated_at <= cleanup_threshold
        ).all()

        comment_count = len(deleted_comments)
        for comment in deleted_comments:
            db.delete(comment)

        db.commit()
        logger.info(f"[Celery] 内容清理完成，删除 {post_count} 个帖子，{comment_count} 条评论")
        return {"posts": post_count, "comments": comment_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 内容清理任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def update_activity_status(self):
    """
    更新活动状态

    根据时间自动更新活动的进行状态
    """
    from app.database import SessionLocal
    from app.models.social import Activity

    db = SessionLocal()
    try:
        now = datetime.now()

        # 即将开始 -> 进行中
        started = db.query(Activity).filter(
            Activity.status == "upcoming",
            Activity.start_time <= now
        ).update({"status": "ongoing"}, synchronize_session=False)

        # 进行中 -> 已结束（有结束时间的活动）
        ended = db.query(Activity).filter(
            Activity.status == "ongoing",
            Activity.end_time.isnot(None),
            Activity.end_time <= now
        ).update({"status": "completed"}, synchronize_session=False)

        db.commit()
        logger.info(f"[Celery] 活动状态更新完成，开始 {started} 个，结束 {ended} 个")
        return {"started": started, "ended": ended}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 活动状态更新失败: {str(e)}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@shared_task
def update_topic_trending(topic_id: int = None):
    """
    更新话题热度（异步任务）

    可以指定单个话题或更新所有话题
    """
    from app.database import SessionLocal
    from app.models.content import Topic, Post
    from sqlalchemy import func

    db = SessionLocal()
    try:
        hot_window = datetime.now() - timedelta(days=7)

        if topic_id:
            topics = [db.query(Topic).filter(Topic.id == topic_id).first()]
            topics = [t for t in topics if t]
        else:
            topics = db.query(Topic).filter(Topic.status == 1).all()

        for topic in topics:
            # 计算话题下帖子的总互动量
            stats = db.query(
                func.count(Post.id).label('post_count'),
                func.sum(Post.views_count).label('total_views'),
                func.sum(Post.likes_count).label('total_likes')
            ).filter(
                Post.topics.contains(topic.name),
                Post.created_at >= hot_window,
                Post.status == 1,
                Post.deleted_at.is_(None)
            ).first()

            # 计算热度
            hot_score = (
                (stats.post_count or 0) * 10 +
                (stats.total_views or 0) * 0.1 +
                (stats.total_likes or 0) * 2
            )

            topic.post_count = stats.post_count or 0
            topic.heat_score = int(hot_score)

        db.commit()
        logger.info(f"[Celery] 话题热度更新完成，处理 {len(topics)} 个话题")
        return {"processed_count": len(topics)}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 话题热度更新失败: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task
def generate_content_report():
    """
    生成内容统计报告（每日任务）
    """
    from app.database import SessionLocal
    from app.models.content import Post, Comment
    from app.models.user import User
    from sqlalchemy import func

    db = SessionLocal()
    try:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        # 昨日统计
        new_posts = db.query(func.count(Post.id)).filter(
            Post.created_at >= yesterday,
            Post.created_at < today
        ).scalar() or 0

        new_comments = db.query(func.count(Comment.id)).filter(
            Comment.created_at >= yesterday,
            Comment.created_at < today
        ).scalar() or 0

        new_users = db.query(func.count(User.id)).filter(
            User.created_at >= yesterday,
            User.created_at < today
        ).scalar() or 0

        total_views = db.query(func.sum(Post.views_count)).filter(
            Post.created_at >= yesterday,
            Post.created_at < today
        ).scalar() or 0

        report = {
            "date": yesterday.strftime("%Y-%m-%d"),
            "new_posts": new_posts,
            "new_comments": new_comments,
            "new_users": new_users,
            "total_views": total_views,
            "generated_at": datetime.now().isoformat()
        }

        logger.info(f"[Celery] 内容报告生成完成: {report}")
        return report

    except Exception as e:
        logger.error(f"[Celery] 内容报告生成失败: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()
