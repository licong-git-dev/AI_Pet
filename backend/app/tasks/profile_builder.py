"""
PetPal - 主人画像 + 长期记忆 周期任务

- rebuild_all_profiles(): 每日重建活跃用户的画像
- decay_memories(): 每日记忆衰减扫描
- weekly_digest_all(): 每周一为活跃分身生成周摘要
"""
from datetime import datetime, timedelta
from celery import shared_task
from loguru import logger
from sqlalchemy import func, distinct


# Celery beat 调度配置见 celery_app.py


@shared_task(name="app.tasks.profile_builder.rebuild_all_profiles")
def rebuild_all_profiles(window_days: int = 30, max_users: int = 5000) -> dict:
    """
    扫描过去 window_days 内有信号的用户，重建画像。
    每日凌晨 4:00 由 beat 触发。
    """
    from app.database import SessionLocal
    from app.models.owner_profile import OwnerSignal
    from app.services import owner_profile_service

    db = SessionLocal()
    success_count, fail_count = 0, 0
    try:
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        user_ids = [
            uid for (uid,) in db.query(distinct(OwnerSignal.user_id))
            .filter(OwnerSignal.recorded_at >= cutoff)
            .limit(max_users)
            .all()
        ]
        logger.info(f"[profile_builder] {len(user_ids)} active users in last {window_days}d")
        for uid in user_ids:
            try:
                owner_profile_service.build_profile(db, user_id=uid, window_days=window_days)
                db.commit()
                success_count += 1
            except Exception as e:
                logger.warning(f"[profile_builder] user={uid} failed: {e}")
                db.rollback()
                fail_count += 1
        return {"success": success_count, "failed": fail_count}
    finally:
        db.close()


@shared_task(name="app.tasks.profile_builder.decay_memories")
def decay_memories() -> dict:
    """
    每日扫描所有未归档记忆，更新有效强度并按阈值归档。
    每日凌晨 3:30 触发。
    """
    from app.database import SessionLocal
    from app.services import memory_service

    db = SessionLocal()
    try:
        return memory_service.decay_pass(db)
    finally:
        db.close()


@shared_task(name="app.tasks.profile_builder.weekly_digest_all")
def weekly_digest_all(max_avatars: int = 10000) -> dict:
    """
    周一早 6 点：为最近 7 天有对话的分身生成周摘要。
    """
    from app.database import SessionLocal
    from app.models.memory import PetMemory
    from app.services import memory_service

    db = SessionLocal()
    built, skipped = 0, 0
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        # 取最近 7 天有过 episodic 记忆的 (avatar, user) 对
        rows = (
            db.query(PetMemory.pet_avatar_id, PetMemory.user_id, func.count())
            .filter(
                PetMemory.memory_type == "episodic",
                PetMemory.created_at >= cutoff,
                PetMemory.is_archived.is_(False),
            )
            .group_by(PetMemory.pet_avatar_id, PetMemory.user_id)
            .having(func.count() >= 3)
            .limit(max_avatars)
            .all()
        )
        logger.info(f"[profile_builder] {len(rows)} avatars eligible for weekly digest")
        for avatar_id, user_id, _ in rows:
            try:
                d = memory_service.build_weekly_digest(
                    db, pet_avatar_id=avatar_id, user_id=user_id
                )
                db.commit()
                built += 1 if d else 0
                if not d:
                    skipped += 1
            except Exception as e:
                logger.warning(f"[profile_builder] digest avatar={avatar_id} failed: {e}")
                db.rollback()
        return {"built": built, "skipped": skipped}
    finally:
        db.close()
