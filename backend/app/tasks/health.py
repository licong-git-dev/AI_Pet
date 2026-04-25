"""
PetPal - 健康相关定时任务

- 疫苗接种提醒
- 驱虫提醒
- 健康指标异常告警
"""
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy import and_
from loguru import logger


@shared_task(bind=True, max_retries=3)
def check_vaccine_reminders(self):
    """
    检查疫苗接种提醒

    查找7天内需要接种疫苗的宠物，发送提醒通知
    """
    from app.database import SessionLocal
    from app.models.health import HealthRecord
    from app.models.pet import Pet
    from app.models.user import User
    from app.models.social import Notification

    db = SessionLocal()
    try:
        now = datetime.now()
        reminder_date = now + timedelta(days=7)

        # 查找即将到期的疫苗记录
        records = db.query(HealthRecord).filter(
            HealthRecord.record_type.in_(["vaccination", "deworming"]),
            HealthRecord.next_date.isnot(None),
            HealthRecord.next_date <= reminder_date,
            HealthRecord.next_date >= now
        ).all()

        sent_count = 0
        for record in records:
            # 获取宠物和用户信息
            pet = db.query(Pet).filter(Pet.id == record.pet_id).first()
            if not pet or pet.deleted_at:
                continue

            user = db.query(User).filter(User.id == pet.owner_id).first()
            if not user or user.status != 1:
                continue

            # 计算剩余天数
            days_left = (record.next_date - now).days

            # 检查是否已发送过提醒
            existing = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.target_type == "health_record",
                Notification.target_id == record.id,
                Notification.created_at >= now - timedelta(days=1)
            ).first()

            if existing:
                continue

            # 构建提醒内容
            record_type_text = "疫苗接种" if record.record_type == "vaccination" else "驱虫"
            content = f"您的宠物「{pet.name}」{record_type_text}即将到期（{days_left}天后），请及时安排。"
            if record.vaccine_name:
                content += f"（{record.vaccine_name}）"

            # 创建通知
            notification = Notification(
                user_id=user.id,
                notify_type="system",
                target_type="health_record",
                target_id=record.id,
                title=f"{record_type_text}提醒",
                content=content
            )
            db.add(notification)
            sent_count += 1

        db.commit()
        logger.info(f"[Celery] 疫苗提醒任务完成，发送 {sent_count} 条提醒")
        return {"sent_count": sent_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 疫苗提醒任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def check_health_alerts(self):
    """
    检查健康指标异常告警

    分析宠物健康数据，检测异常情况
    """
    from app.database import SessionLocal
    from app.models.health import HealthRecord
    from app.models.pet import Pet
    from app.models.user import User
    from app.models.social import Notification

    db = SessionLocal()
    try:
        # 检查最近的高风险健康记录
        recent_time = datetime.now() - timedelta(hours=24)

        high_risk_records = db.query(HealthRecord).filter(
            HealthRecord.risk_level == "high",
            HealthRecord.created_at >= recent_time
        ).all()

        alert_count = 0
        for record in high_risk_records:
            pet = db.query(Pet).filter(Pet.id == record.pet_id).first()
            if not pet or pet.deleted_at:
                continue

            user = db.query(User).filter(User.id == pet.owner_id).first()
            if not user or user.status != 1:
                continue

            # 检查是否已发送过告警
            existing = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.target_type == "health_alert",
                Notification.target_id == record.id
            ).first()

            if existing:
                continue

            # 创建告警通知
            notification = Notification(
                user_id=user.id,
                notify_type="system",
                target_type="health_alert",
                target_id=record.id,
                title="健康风险提醒",
                content=f"您的宠物「{pet.name}」的健康分析显示存在较高风险，建议尽快就医检查。"
            )
            db.add(notification)
            alert_count += 1

        db.commit()
        logger.info(f"[Celery] 健康告警任务完成，发送 {alert_count} 条告警")
        return {"alert_count": alert_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 健康告警任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task
def send_health_report(user_id: int, pet_id: int):
    """
    发送宠物健康报告（异步任务）
    """
    from app.database import SessionLocal
    from app.models.health import HealthRecord
    from app.models.pet import Pet
    from app.models.social import Notification

    db = SessionLocal()
    try:
        pet = db.query(Pet).filter(Pet.id == pet_id).first()
        if not pet:
            return {"error": "Pet not found"}

        # 获取最近30天的健康记录
        recent_time = datetime.now() - timedelta(days=30)
        records = db.query(HealthRecord).filter(
            HealthRecord.pet_id == pet_id,
            HealthRecord.created_at >= recent_time
        ).all()

        # 生成报告摘要
        record_count = len(records)
        avg_score = sum(r.health_score or 0 for r in records) / max(record_count, 1)

        notification = Notification(
            user_id=user_id,
            notify_type="system",
            target_type="pet",
            target_id=pet_id,
            title=f"{pet.name}的月度健康报告",
            content=f"本月共记录 {record_count} 条健康数据，平均健康评分 {avg_score:.1f} 分。"
        )
        db.add(notification)
        db.commit()

        logger.info(f"[Celery] 健康报告已发送给用户 {user_id}")
        return {"success": True}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 发送健康报告失败: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()
