"""
PetPal - 用户相关定时任务

- 积分过期处理
- 签到连续性重置
- 生日祝福
- 用户活跃度统计
"""
from datetime import datetime, timedelta
from celery import shared_task
from loguru import logger


@shared_task(bind=True, max_retries=3)
def expire_points(self):
    """
    处理过期积分

    将已过期的积分标记为过期，并扣减用户余额
    """
    from app.database import SessionLocal
    from app.models.points import PointsRecord
    from app.models.user import User
    from app.models.social import Notification

    db = SessionLocal()
    try:
        now = datetime.now()

        # 查找已过期但未处理的积分记录
        expired_records = db.query(PointsRecord).filter(
            PointsRecord.expire_at <= now,
            PointsRecord.is_expired == 0,
            PointsRecord.points > 0  # 只处理获得的积分
        ).all()

        expired_count = 0
        total_expired_points = 0

        for record in expired_records:
            user = db.query(User).filter(User.id == record.user_id).first()
            if not user:
                continue

            # 标记积分过期
            record.is_expired = 1

            # 计算实际过期积分（不能超过用户当前余额）
            expired_points = min(record.points, user.points)
            if expired_points <= 0:
                continue

            # 创建过期扣减记录
            expire_record = PointsRecord(
                user_id=user.id,
                points=-expired_points,
                balance=user.points - expired_points,
                source_type="expire",
                source_id=record.id,
                description=f"积分过期（原记录ID: {record.id}）"
            )
            db.add(expire_record)

            # 扣减用户积分
            user.points -= expired_points
            total_expired_points += expired_points
            expired_count += 1

            # 发送通知
            notification = Notification(
                user_id=user.id,
                notify_type="system",
                title="积分过期提醒",
                content=f"您有 {expired_points} 积分已过期，请注意使用剩余积分。"
            )
            db.add(notification)

        db.commit()
        logger.info(f"[Celery] 积分过期任务完成，处理 {expired_count} 条记录，共 {total_expired_points} 积分")
        return {"expired_count": expired_count, "total_points": total_expired_points}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 积分过期任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def reset_checkin_streaks(self):
    """
    重置断签用户的连续签到天数

    检查超过48小时未签到的用户，重置其连续签到天数
    """
    import redis
    from app.config import settings

    try:
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)

        # 获取所有签到streak记录
        pattern = "checkin_streak:*"
        cursor = 0
        reset_count = 0

        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=100)

            for key in keys:
                user_id = key.split(":")[-1]
                today = datetime.now().strftime("%Y-%m-%d")
                yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                today_key = f"checkin:{user_id}:{today}"
                yesterday_key = f"checkin:{user_id}:{yesterday}"

                # 如果今天和昨天都没签到，重置连续天数
                if not redis_client.exists(today_key) and not redis_client.exists(yesterday_key):
                    redis_client.delete(key)
                    reset_count += 1

            if cursor == 0:
                break

        logger.info(f"[Celery] 签到连续性重置完成，重置 {reset_count} 个用户")
        return {"reset_count": reset_count}

    except Exception as e:
        logger.error(f"[Celery] 签到重置任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_birthday_greetings(self):
    """
    发送生日祝福

    检查当天生日的用户，发送祝福并赠送积分
    """
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.points import PointsRecord
    from app.models.social import Notification

    db = SessionLocal()
    try:
        today = datetime.now()
        today_month_day = (today.month, today.day)

        # 查找今天生日的用户
        users = db.query(User).filter(
            User.status == 1,
            User.birthday.isnot(None)
        ).all()

        birthday_users = [
            u for u in users
            if u.birthday and (u.birthday.month, u.birthday.day) == today_month_day
        ]

        greeting_count = 0
        birthday_points = 100  # 生日赠送积分

        for user in birthday_users:
            # 赠送积分
            points_record = PointsRecord(
                user_id=user.id,
                points=birthday_points,
                balance=user.points + birthday_points,
                source_type="birthday",
                description="生日快乐！祝您和宠物度过美好的一天"
            )
            db.add(points_record)
            user.points += birthday_points

            # 发送祝福通知
            notification = Notification(
                user_id=user.id,
                notify_type="system",
                title="🎂 生日快乐！",
                content=f"亲爱的 {user.nickname}，祝您生日快乐！我们送您 {birthday_points} 积分作为生日礼物~"
            )
            db.add(notification)
            greeting_count += 1

        db.commit()
        logger.info(f"[Celery] 生日祝福任务完成，发送 {greeting_count} 个祝福")
        return {"greeting_count": greeting_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 生日祝福任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task
def update_user_statistics(user_id: int):
    """
    更新用户统计数据（异步任务）

    重新计算用户的帖子数、粉丝数等统计信息
    """
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.content import Post, Comment
    from app.models.social import Follow
    from sqlalchemy import func

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        # 统计帖子数
        posts_count = db.query(func.count(Post.id)).filter(
            Post.author_id == user_id,
            Post.deleted_at.is_(None),
            Post.status == 1
        ).scalar() or 0

        # 统计粉丝数
        followers_count = db.query(func.count(Follow.id)).filter(
            Follow.following_id == user_id,
            Follow.status == 1
        ).scalar() or 0

        # 统计关注数
        following_count = db.query(func.count(Follow.id)).filter(
            Follow.follower_id == user_id,
            Follow.status == 1
        ).scalar() or 0

        # 统计获赞数
        likes_count = db.query(func.sum(Post.likes_count)).filter(
            Post.author_id == user_id,
            Post.deleted_at.is_(None)
        ).scalar() or 0

        # 更新用户统计
        user.posts_count = posts_count
        user.followers_count = followers_count
        user.following_count = following_count
        user.likes_count = likes_count

        db.commit()
        logger.info(f"[Celery] 用户统计更新完成: user_id={user_id}")
        return {"success": True}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 用户统计更新失败: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()
