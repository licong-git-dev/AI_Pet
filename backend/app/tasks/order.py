"""
PetPal - 订单相关定时任务

- 超时未支付订单取消
- 自动确认收货
- 退款处理
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from celery import shared_task
from loguru import logger


@shared_task(bind=True, max_retries=3)
def cancel_unpaid_orders(self):
    """
    取消超时未支付的订单

    超过30分钟未支付的订单自动取消，恢复库存
    """
    from app.database import SessionLocal
    from app.models.shop import Order, OrderItem, Product

    db = SessionLocal()
    try:
        timeout = datetime.now() - timedelta(minutes=30)

        # 查找超时未支付订单
        orders = db.query(Order).filter(
            Order.status == "pending",
            Order.created_at <= timeout
        ).all()

        cancelled_count = 0
        for order in orders:
            # 恢复库存
            items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
            for item in items:
                product = db.query(Product).filter(Product.id == item.product_id).first()
                if product:
                    product.stock += item.quantity
                    product.sales -= item.quantity

            # 更新订单状态
            order.status = "cancelled"
            order.cancel_reason = "支付超时自动取消"
            order.cancelled_at = datetime.now()
            cancelled_count += 1

        db.commit()
        logger.info(f"[Celery] 取消超时订单任务完成，取消 {cancelled_count} 个订单")
        return {"cancelled_count": cancelled_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 取消超时订单任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def auto_confirm_orders(self):
    """
    自动确认收货

    发货超过15天的订单自动确认收货
    """
    from app.database import SessionLocal
    from app.models.shop import Order
    from app.models.social import Notification

    db = SessionLocal()
    try:
        auto_confirm_days = 15
        confirm_deadline = datetime.now() - timedelta(days=auto_confirm_days)

        # 查找需要自动确认的订单
        orders = db.query(Order).filter(
            Order.status == "shipped",
            Order.shipped_at <= confirm_deadline
        ).all()

        confirmed_count = 0
        for order in orders:
            order.status = "received"
            order.received_at = datetime.now()
            order.auto_confirmed = 1

            # 通知用户
            notification = Notification(
                user_id=order.user_id,
                notify_type="system",
                target_type="order",
                target_id=order.id,
                title="订单自动确认收货",
                content=f"您的订单 {order.order_no} 已自动确认收货，如有问题请联系客服。"
            )
            db.add(notification)
            confirmed_count += 1

        db.commit()
        logger.info(f"[Celery] 自动确认收货任务完成，确认 {confirmed_count} 个订单")
        return {"confirmed_count": confirmed_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 自动确认收货任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=300)
    finally:
        db.close()


@shared_task(bind=True, max_retries=3)
def process_pending_refunds(self):
    """
    处理待处理的退款申请

    自动处理已审核通过的退款
    """
    from app.database import SessionLocal
    from app.models.shop import Order, RefundRequest
    from app.models.social import Notification
    from app.services.payment_service import payment_service

    db = SessionLocal()
    try:
        # 查找已审核通过待退款的申请
        refunds = db.query(RefundRequest).filter(
            RefundRequest.status == "approved"
        ).all()

        processed_count = 0
        failed_count = 0

        for refund in refunds:
            order = db.query(Order).filter(Order.id == refund.order_id).first()
            if not order:
                continue

            # 余额支付直接退还积分
            if order.pay_method == "balance":
                from app.models.user import User
                user = db.query(User).filter(User.id == order.user_id).first()
                if user:
                    refund_points = int(Decimal(str(refund.refund_amount)) * 100)
                    user.points += refund_points
                    refund.status = "completed"
                    refund.completed_at = datetime.now()
                    order.status = "refunded"
                    order.refunded_at = datetime.now()

                    notification = Notification(
                        user_id=order.user_id,
                        notify_type="system",
                        target_type="order",
                        target_id=order.id,
                        title="退款成功",
                        content=f"您的订单 {order.order_no} 退款已完成，已退还 {refund_points} 积分。"
                    )
                    db.add(notification)
                    processed_count += 1
                continue

            # 调用支付接口进行退款（支付宝/微信）
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                refund_result = loop.run_until_complete(
                    payment_service.refund(
                        order_no=order.order_no,
                        refund_no=refund.refund_no,
                        refund_amount=Decimal(str(refund.refund_amount)),
                        total_amount=Decimal(str(order.pay_amount)),
                        payment_method=order.pay_method,
                        reason=refund.reason or "用户申请退款"
                    )
                )
                loop.close()

                if refund_result.success:
                    refund.status = "completed"
                    refund.completed_at = datetime.now()
                    refund.trade_no = refund_result.refund_no

                    order.status = "refunded"
                    order.refunded_at = datetime.now()

                    notification = Notification(
                        user_id=order.user_id,
                        notify_type="system",
                        target_type="order",
                        target_id=order.id,
                        title="退款成功",
                        content=f"您的订单 {order.order_no} 退款已完成，退款金额 ¥{refund.refund_amount:.2f}。"
                    )
                    db.add(notification)
                    processed_count += 1
                    logger.info(f"[Celery] 退款成功: order_no={order.order_no}, refund_no={refund.refund_no}")
                else:
                    # 退款失败，记录错误但不改变状态，等待下次重试
                    failed_count += 1
                    logger.warning(f"[Celery] 退款失败: order_no={order.order_no}, error={refund_result.error_message}")

            except Exception as refund_error:
                failed_count += 1
                logger.error(f"[Celery] 退款异常: order_no={order.order_no}, error={str(refund_error)}")
                continue

        db.commit()
        logger.info(f"[Celery] 退款处理任务完成，成功 {processed_count} 个，失败 {failed_count} 个")
        return {"processed_count": processed_count, "failed_count": failed_count}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 退款处理任务失败: {str(e)}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()


@shared_task
def notify_order_status(order_id: int, status: str):
    """
    发送订单状态变更通知（异步任务）
    """
    from app.database import SessionLocal
    from app.models.shop import Order
    from app.models.social import Notification

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": "Order not found"}

        status_text = {
            "paid": "已支付",
            "shipped": "已发货",
            "received": "已收货",
            "completed": "已完成",
            "cancelled": "已取消",
            "refunding": "退款中",
            "refunded": "已退款"
        }

        notification = Notification(
            user_id=order.user_id,
            notify_type="system",
            target_type="order",
            target_id=order_id,
            title="订单状态更新",
            content=f"您的订单 {order.order_no} 状态已更新为：{status_text.get(status, status)}"
        )
        db.add(notification)
        db.commit()

        # 发送实时推送
        try:
            from app.websocket import manager
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                manager.send_order_update(order.user_id, order_id, status)
            )
        except Exception:
            pass  # WebSocket 推送失败不影响主流程

        logger.info(f"[Celery] 订单状态通知已发送: order_id={order_id}, status={status}")
        return {"success": True}

    except Exception as e:
        db.rollback()
        logger.error(f"[Celery] 发送订单通知失败: {str(e)}")
        return {"error": str(e)}
    finally:
        db.close()
