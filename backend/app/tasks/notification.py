"""
PetPal - 通知相关定时任务

- 活动提醒
- 批量推送
- 通知清理
"""
from datetime import datetime, timedelta
from celery import shared_task
from loguru import logger


@shared_task(bind=True, max_retries=3)
def send_activity_reminders(self):
    """
    发送活动开始提醒

    活动开始前24小时和1小时分别发送提醒
    """
    from app.database import SessionLocal
    from app.models.social import Activity, ActivityParticipant, Notification
    from app.models.user import User

    db = SessionLocal()
    try:
        now = datetime.now()

        # 24小时提醒
        reminder_24h_start = now + timedelta(hours=23, minutes=30)
        reminder_24h_end = now + timedelta(hours=24, minutes=30)

        # 1小时提醒
        reminder_1h_start = now + timedelta(minutes=30)
        reminder_1h_end = now + timedelta(hours=1, minutes=30)

        sent_count = 0

        # 查找需要24小时提醒的活动
        activities_24h = db.query(Activity).filter(
            Activity.status == "upcoming",
            Activity.start_time >= reminder_24h_start,
            Activity.start_time <= reminder_24h_end
        ).all()

        for activity in activities_24h:
            participants = db.query(ActivityParticipant).filter(
                ActivityParticipant.activity_id == activity.id,
                ActivityParticipant.status == "registered"
            ).all()

            for p in participants:
                # 检查是否已发送
                existing = db.query(Notification).filter(
                    Notification.user_id == p.user_id,
                    Notification.target_type == "activity_reminder_24h",
                    Notification.target_id == activity.id
                ).first()

                if existing:
                    continue

                notification = Notification(
                    user_id=p.user_id,
                    notify_type="system",
                    target_type="activity_reminder_24h",
                    target_id=activity.id,
                    title="活动提醒",
                    content=f"您报名的活动「{activity.title}」将于明天开始，请做好准备！"
                )
                db.add(notification)
                sent_count += 1

        # 查找需要1小时提醒的活动
        activities_1h = db.query(Activity).filter(
            Activity.status == "upcoming",
            Activity.start_time >= reminder_1h_start,
            Activity.start_time <= reminder_1h_end
        ).all()

        for activity in activities_1h:
            participants = db.query(ActivityParticipant).filter(
                ActivityParticipant.activity_id == activity.id,
                ActivityParticipant.status == "registered"
            ).all()

            for p in participants:
                existing = db.query(Notification).filter(
                    Notification.user_id == p.user_id,
                    Notification.target_type == "activity_reminder_1h",
                    Notification.target_id == activity.id
                ).first()

                if existing:
                    continue

                notification = Notification(
                    user_id=p.user_id,
                    notify_type="system",
                    target_type="activity_reminder_1h",
                    target_id=activity.id,
                    title="活动即将开始",
                    content=f"您报名的活动「{activity.title}」将于1小时后开始，请准时到达！"
                )
                db.add(notification)
                sent_count += 1

                # 发送实时推送
                try:
                    from app.websocket import manager
                    import asyncio
                    asyncio.get_event_loop().run_until_complete(
                        manager.send_notification(p.user_id, {
                            "type": "activity_reminder",
                            "activity_id": activity.id,
                            "title": activity.title,
                            "start_time": activity.start_time.isoformat()
                        })
                    )
                except Exception:
                    pass

        db.commit()
        logger.info(f"[Celery] 活动提醒任务完成，发送 {sent_count} 条提醒")
        return {"sent_count": sent_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 活动提醒任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@shared_task
def send_push_notification(user_id: int, title: str, content: str, data: dict = None):
    """
    发送推送通知（异步任务）

    支持 WebSocket 实时推送和第三方推送服务
    """
    from app.database import SessionLocal
    from app.models.user import User
    from app.models.user_settings import UserSettings
    from app.models.social import Notification

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        # 检查用户推送设置
        settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if settings and not settings.push_enabled:
            return {"skipped": "Push disabled by user"}

        # 创建通知记录
        notification = Notification(
            user_id=user_id,
            notify_type="push",
            title=title,
            content=content
        )
        db.add(notification)
        db.commit()

        # WebSocket 实时推送
        try:
            from app.websocket import manager
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                manager.send_notification(user_id, {
                    "id": notification.id,
                    "title": title,
                    "content": content,
                    "data": data
                })
            )
        except Exception as e:
            logger.warning(f"WebSocket 推送失败: {str(e)}")

        # TODO: 集成第三方推送服务（极光、个推等）

        logger.info(f"[Celery] 推送通知已发送: user_id={user_id}, title={title}")
        return {"success": True, "notification_id": notification.id}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 推送通知失败: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task
def send_batch_notification(user_ids: list, title: str, content: str):
    """
    批量发送通知（异步任务）
    """
    from app.database import SessionLocal
    from app.models.social import Notification

    db = SessionLocal()
    try:
        notifications = []
        for user_id in user_ids:
            notification = Notification(
                user_id=user_id,
                notify_type="system",
                title=title,
                content=content
            )
            notifications.append(notification)

        db.bulk_save_objects(notifications)
        db.commit()

        # 批量 WebSocket 推送
        try:
            from app.websocket import manager
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                manager.send_to_users(user_ids, {
                    "type": "notification",
                    "data": {"title": title, "content": content}
                })
            )
        except Exception:
            pass

        logger.info(f"[Celery] 批量通知已发送: {len(user_ids)} 个用户")
        return {"success": True, "count": len(user_ids)}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 批量通知失败: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def cleanup_old_notifications(self):
    """
    清理过期通知

    删除90天前的已读通知
    """
    from app.database import SessionLocal
    from app.models.social import Notification

    db = SessionLocal()
    try:
        cleanup_threshold = datetime.now() - timedelta(days=90)

        deleted = db.query(Notification).filter(
            Notification.is_read == 1,
            Notification.created_at <= cleanup_threshold
        ).delete(synchronize_session=False)

        db.commit()
        logger.info(f"[Celery] 通知清理完成，删除 {deleted} 条过期通知")
        return {"deleted_count": deleted}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 通知清理任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task
def send_sms_notification(phone: str, template: str, params: dict = None):
    """
    发送短信通知（异步任务）
    """
    from app.services.sms_service import SMSService

    try:
        sms_service = SMSService()
        result = sms_service.send_template_sms(phone, template, params or {})

        if result.get("success"):
            logger.info(f"[Celery] 短信发送成功: phone={phone}, template={template}")
            return {"success": True}
        else:
            logger.warning(f"[Celery] 短信发送失败: {result.get('error')}")
            return {"error": result.get("error")}

    except Exception as e:
        logger.error(f"[Celery] 短信发送异常: {str(e)}")
        return {"error": str(e)}
