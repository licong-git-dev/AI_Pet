"""
PetPal - 宠物数字分身异步任务

- 表情包生成轮询（DashScope Wanx 异步任务）
- 使用 Celery self.retry 非阻塞模式替代 time.sleep 轮询
"""
import httpx
from celery import shared_task
from celery.exceptions import Retry
from loguru import logger


@shared_task(bind=True, max_retries=30, default_retry_delay=3)
def process_sticker_generation(self, sticker_id: int):
    """
    异步轮询 DashScope Wanx 图像生成任务状态。

    使用 Celery self.retry(countdown=3) 非阻塞模式：
    - 每次执行只查询一次状态
    - 未完成则通过 retry 调度下一次检查，释放 worker
    - 最多重试 30 次（约 90 秒）
    """
    from app.database import SessionLocal
    from app.models.avatar import PetSticker
    from app.config import settings

    db = SessionLocal()
    try:
        # 每次重试都重新查询，避免操作过期对象
        sticker = db.query(PetSticker).filter(PetSticker.id == sticker_id).first()
        if not sticker:
            logger.warning(f"表情包记录不存在: {sticker_id}")
            return

        if not sticker.task_id:
            logger.warning(f"表情包无 task_id: {sticker_id}")
            sticker.status = "failed"
            sticker.error_message = "缺少任务ID"
            db.commit()
            return

        # 已经是终态，无需继续
        if sticker.status in ("completed", "failed"):
            return

        task_id = sticker.task_id
        status = _poll_dashscope_task(task_id, settings.dashscope_api_key)

        if status["result"] == "SUCCEEDED":
            if status.get("image_url"):
                sticker.sticker_url = status["image_url"]
                sticker.status = "completed"
                db.commit()
                logger.info(f"表情包生成成功: sticker_id={sticker_id}")
                _notify_user_sync(sticker.user_id, sticker_id)
            else:
                sticker.status = "failed"
                sticker.error_message = "生成结果为空"
                db.commit()
            return

        elif status["result"] == "FAILED":
            sticker.status = "failed"
            sticker.error_message = status.get("error", "生成失败")[:500]
            db.commit()
            logger.error(f"表情包生成失败: sticker_id={sticker_id}, error={status.get('error')}")
            return

        elif status["result"] == "PENDING":
            # 仍在处理中 → 调度下次检查
            logger.debug(
                f"表情包生成中: sticker_id={sticker_id}, "
                f"attempt={self.request.retries + 1}/{self.max_retries}"
            )
            raise self.retry(countdown=3)

        elif status["result"] == "HTTP_ERROR":
            # HTTP 级别错误，重试
            raise self.retry(countdown=5)

    except Retry:
        # Celery Retry 异常必须向上传播
        raise
    except self.MaxRetriesExceededError:
        # 超过最大重试次数 → 标记超时
        _mark_sticker_timeout(db, sticker_id)
        raise
    except Exception as e:
        logger.error(f"表情包任务异常: {str(e)}")
        _mark_sticker_failed(db, sticker_id, f"任务异常: {str(e)[:200]}")
    finally:
        db.close()


def _poll_dashscope_task(task_id: str, api_key: str) -> dict:
    """
    查询 DashScope 任务状态（同步）。

    Returns:
        {"result": "SUCCEEDED/FAILED/PENDING/HTTP_ERROR", "image_url": ..., "error": ...}
    """
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {api_key}"}
            )

            if response.status_code != 200:
                logger.warning(f"查询任务状态 HTTP {response.status_code}")
                return {"result": "HTTP_ERROR"}

            data = response.json()

            # DashScope 有时 HTTP 200 但 body 含业务错误码
            if data.get("code") and str(data.get("code")) not in ("200", ""):
                return {
                    "result": "FAILED",
                    "error": f"[{data.get('code')}] {data.get('message', '未知错误')}"
                }

            output = data.get("output", {})
            status = output.get("task_status", "UNKNOWN")

            if status == "SUCCEEDED":
                results = output.get("results", [])
                image_url = results[0].get("url") if results else None
                return {"result": "SUCCEEDED", "image_url": image_url}

            elif status == "FAILED":
                error_msg = output.get("message", "生成失败")
                return {"result": "FAILED", "error": error_msg}

            else:
                # PENDING / RUNNING / UNKNOWN
                return {"result": "PENDING"}

    except httpx.HTTPError as e:
        logger.warning(f"HTTP 请求异常: {str(e)}")
        return {"result": "HTTP_ERROR"}


def _mark_sticker_timeout(db, sticker_id: int):
    """标记表情包超时"""
    try:
        from app.models.avatar import PetSticker
        sticker = db.query(PetSticker).filter(PetSticker.id == sticker_id).first()
        if sticker and sticker.status not in ("completed", "failed"):
            sticker.status = "failed"
            sticker.error_message = "生成超时"
            db.commit()
            logger.error(f"表情包生成超时: sticker_id={sticker_id}")
    except Exception:
        pass


def _mark_sticker_failed(db, sticker_id: int, error_msg: str):
    """标记表情包失败"""
    try:
        from app.models.avatar import PetSticker
        sticker = db.query(PetSticker).filter(PetSticker.id == sticker_id).first()
        if sticker and sticker.status not in ("completed", "failed"):
            sticker.status = "failed"
            sticker.error_message = error_msg
            db.commit()
    except Exception:
        pass


def _notify_user_sync(user_id: int, sticker_id: int):
    """
    同步方式通知用户表情包生成完成。
    通过 Redis pub/sub 发布消息，WebSocket 服务端监听并转发给用户。
    """
    try:
        import redis
        import json
        from app.config import settings

        r = redis.Redis.from_url(settings.redis_url)
        message = json.dumps({
            "type": "sticker_ready",
            "user_id": user_id,
            "data": {"sticker_id": sticker_id},
        })
        r.publish("ws_notifications", message)
        logger.debug(f"已发布通知: user_id={user_id}, sticker_id={sticker_id}")
    except ImportError:
        pass
    except Exception:
        pass
