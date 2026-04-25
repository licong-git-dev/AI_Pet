"""
PetPal - Celery 异步任务配置

配置 Celery 应用用于：
- 定时任务（疫苗提醒、积分过期等）
- 异步任务（邮件发送、推送通知等）
- 后台任务（数据统计、报表生成等）
"""
from celery import Celery
from celery.schedules import crontab
from app.config import settings

# 创建 Celery 应用
celery_app = Celery(
    "petpal",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.health",
        "app.tasks.order",
        "app.tasks.user",
        "app.tasks.content",
        "app.tasks.notification",
        "app.tasks.avatar",
        "app.tasks.profile_builder",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务结果
    result_expires=3600,  # 结果保留1小时
    task_track_started=True,

    # 任务执行
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=4,

    # 任务重试
    task_default_retry_delay=60,
    task_max_retries=3,

    # 定时任务配置
    beat_schedule={
        # ==================== 健康相关 ====================
        "check-vaccine-reminders": {
            "task": "app.tasks.health.check_vaccine_reminders",
            "schedule": crontab(hour=9, minute=0),  # 每天9点
            "options": {"queue": "health"}
        },
        "check-health-alerts": {
            "task": "app.tasks.health.check_health_alerts",
            "schedule": crontab(hour="*/6"),  # 每6小时
            "options": {"queue": "health"}
        },

        # ==================== 订单相关 ====================
        "cancel-unpaid-orders": {
            "task": "app.tasks.order.cancel_unpaid_orders",
            "schedule": crontab(minute="*/30"),  # 每30分钟
            "options": {"queue": "order"}
        },
        "auto-confirm-orders": {
            "task": "app.tasks.order.auto_confirm_orders",
            "schedule": crontab(hour=2, minute=0),  # 每天凌晨2点
            "options": {"queue": "order"}
        },
        "process-refunds": {
            "task": "app.tasks.order.process_pending_refunds",
            "schedule": crontab(minute="*/15"),  # 每15分钟
            "options": {"queue": "order"}
        },

        # ==================== 用户相关 ====================
        "expire-points": {
            "task": "app.tasks.user.expire_points",
            "schedule": crontab(hour=0, minute=5),  # 每天0:05
            "options": {"queue": "user"}
        },
        "reset-checkin-streaks": {
            "task": "app.tasks.user.reset_checkin_streaks",
            "schedule": crontab(hour=0, minute=10),  # 每天0:10
            "options": {"queue": "user"}
        },
        "send-birthday-greetings": {
            "task": "app.tasks.user.send_birthday_greetings",
            "schedule": crontab(hour=8, minute=0),  # 每天8点
            "options": {"queue": "user"}
        },

        # ==================== 内容相关 ====================
        "update-hot-posts": {
            "task": "app.tasks.content.update_hot_posts",
            "schedule": crontab(hour="*/2"),  # 每2小时
            "options": {"queue": "content"}
        },
        "cleanup-deleted-content": {
            "task": "app.tasks.content.cleanup_deleted_content",
            "schedule": crontab(hour=3, minute=0),  # 每天凌晨3点
            "options": {"queue": "content"}
        },

        # ==================== 活动相关 ====================
        "send-activity-reminders": {
            "task": "app.tasks.notification.send_activity_reminders",
            "schedule": crontab(hour="*/1"),  # 每小时
            "options": {"queue": "notification"}
        },
        "update-activity-status": {
            "task": "app.tasks.content.update_activity_status",
            "schedule": crontab(minute="*/10"),  # 每10分钟
            "options": {"queue": "content"}
        },

        # ==================== 分身：记忆 + 画像 ====================
        "decay-memories": {
            "task": "app.tasks.profile_builder.decay_memories",
            "schedule": crontab(hour=3, minute=30),  # 每日 03:30
            "options": {"queue": "avatar"}
        },
        "rebuild-owner-profiles": {
            "task": "app.tasks.profile_builder.rebuild_all_profiles",
            "schedule": crontab(hour=4, minute=0),  # 每日 04:00
            "options": {"queue": "avatar"}
        },
        "weekly-memory-digest": {
            "task": "app.tasks.profile_builder.weekly_digest_all",
            "schedule": crontab(hour=6, minute=0, day_of_week=1),  # 每周一 06:00
            "options": {"queue": "avatar"}
        },
    },

    # 任务队列配置
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "health": {"exchange": "health", "routing_key": "health"},
        "order": {"exchange": "order", "routing_key": "order"},
        "user": {"exchange": "user", "routing_key": "user"},
        "content": {"exchange": "content", "routing_key": "content"},
        "notification": {"exchange": "notification", "routing_key": "notification"},
        "avatar": {"exchange": "avatar", "routing_key": "avatar"},
    },
    task_default_queue="default",
)


# 启动命令示例：
# Worker: celery -A app.celery_app worker -l info -Q default,health,order,user,content,notification
# Beat: celery -A app.celery_app beat -l info
