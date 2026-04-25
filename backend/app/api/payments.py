"""
PetPal - 支付回调API

处理支付平台的异步通知：
- 支付宝回调
- 微信支付回调
- 支付状态查询
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from loguru import logger

from app.database import get_db
from app.models.user import User
from app.models.points import PointsRechargeOrder
from app.models.membership import MembershipOrder
from app.models.shop import Order
from app.models.social import Notification
from app.services.payment_service import payment_service, AlipayService, WechatPayService
from app.services.points_recharge import fulfill_recharge_order
from app.services.membership import fulfill_membership_order
from app.utils.deps import get_current_user

router = APIRouter()


def _amount_matches(actual: float, expected: str) -> bool:
    """比较回调金额和订单金额，精确到分。"""
    try:
        actual_cents = int((Decimal(str(actual)) * Decimal("100")).quantize(Decimal("1")))
        expected_cents = int((Decimal(expected) * Decimal("100")).quantize(Decimal("1")))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return actual_cents == expected_cents


def _payment_fields(pay_method: str, trade_no: str) -> dict:
    """兼容订单模型中两组支付字段命名。"""
    return {
        "pay_method": pay_method,
        "pay_type": pay_method,
        "trade_no": trade_no,
        "pay_trade_no": trade_no,
        "paid_at": datetime.now(),
        "pay_time": datetime.now(),
    }


def _apply_model_fields(model, values: dict) -> None:
    for field, value in values.items():
        if hasattr(model, field):
            setattr(model, field, value)


def _load_payable_order(db: Session, order_no: str):
    order = db.query(Order).filter(Order.order_no == order_no).first()
    if order:
        return order, "order"

    recharge_order = db.query(PointsRechargeOrder).filter(PointsRechargeOrder.order_no == order_no).first()
    if recharge_order:
        return recharge_order, "recharge"

    membership_order = db.query(MembershipOrder).filter(MembershipOrder.order_no == order_no).first()
    if membership_order:
        return membership_order, "membership"

    return None, None


def _mark_recharge_paid(order: PointsRechargeOrder, pay_method: str, trade_no: str, db: Session) -> None:
    _apply_model_fields(order, _payment_fields(pay_method, trade_no))
    order.status = "paid"
    fulfill_recharge_order(order, db)


def _mark_membership_paid(order: MembershipOrder, pay_method: str, trade_no: str, db: Session) -> None:
    if order.fulfilled_at is not None:
        return
    _apply_model_fields(order, _payment_fields(pay_method, trade_no))
    order.status = "paid"
    fulfill_membership_order(order, db)


@router.post("/alipay/notify", summary="支付宝异步通知")
async def alipay_notify(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    处理支付宝异步通知

    支付宝会在支付成功后向此接口发送通知
    """
    try:
        # 获取通知参数
        form_data = await request.form()
        params = dict(form_data)

        logger.info(f"收到支付宝通知: {params.get('out_trade_no')}")

        # 验证签名
        alipay = AlipayService()
        if not alipay.verify_notify(params.copy()):
            logger.warning("支付宝通知签名验证失败")
            return PlainTextResponse("fail")

        # 获取关键参数
        out_trade_no = params.get("out_trade_no")
        trade_no = params.get("trade_no")
        trade_status = params.get("trade_status")
        total_amount = params.get("total_amount")

        # 查找订单
        order, order_type = _load_payable_order(db, out_trade_no)
        if not order:
            logger.warning(f"订单不存在: {out_trade_no}")
            return PlainTextResponse("success")  # 返回success避免重复通知

        # 检查订单状态，避免重复处理
        if order.status != "pending":
            logger.info(f"订单已处理: {out_trade_no}, status={order.status}")
            return PlainTextResponse("success")

        # 处理支付结果
        if trade_status in ["TRADE_SUCCESS", "TRADE_FINISHED"]:
            if not trade_no:
                logger.error(f"支付宝通知缺少交易号: {out_trade_no}")
                return PlainTextResponse("fail")

            if not total_amount or not _amount_matches(order.pay_amount, total_amount):
                logger.error(f"支付宝金额不匹配: order={order.pay_amount}, notify={total_amount}")
                return PlainTextResponse("fail")

            if order_type == "recharge":
                _mark_recharge_paid(order, "alipay", trade_no, db)
                logger.info(f"充值订单支付成功: {out_trade_no}")
            elif order_type == "membership":
                _mark_membership_paid(order, "alipay", trade_no, db)
                logger.info(f"会员订单支付成功: {out_trade_no}")
            else:
                _apply_model_fields(order, _payment_fields("alipay", trade_no))
                order.status = "paid"

                notification = Notification(
                    user_id=order.user_id,
                    notify_type="system",
                    target_type="order",
                    target_id=order.id,
                    title="支付成功",
                    content=f"您的订单 {order.order_no} 已支付成功，金额 ¥{total_amount}"
                )
                db.add(notification)

                logger.info(f"订单支付成功: {out_trade_no}")

        db.commit()

        # 异步发送WebSocket通知
        try:
            from app.websocket import manager
            import asyncio
            asyncio.create_task(
                manager.send_order_update(order.user_id, order.id, "paid", {
                    "order_no": order.order_no,
                    "amount": str(total_amount)
                })
            )
        except Exception as e:
            logger.warning(f"WebSocket通知发送失败(支付宝): {str(e)}")

        return PlainTextResponse("success")

    except Exception as e:
        logger.error(f"处理支付宝通知失败: {str(e)}")
        return PlainTextResponse("fail")


@router.post("/wechat/notify", summary="微信支付异步通知")
async def wechat_notify(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    处理微信支付异步通知
    """
    try:
        # 获取XML数据
        body = await request.body()
        xml_data = body.decode("utf-8")

        logger.info("收到微信支付通知")

        # 验证签名
        wechat = WechatPayService()
        valid, data = wechat.verify_notify(xml_data)

        if not valid:
            logger.warning("微信支付通知签名验证失败")
            return PlainTextResponse(
                '<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[签名失败]]></return_msg></xml>'
            )

        # 检查业务结果
        if data.get("return_code") != "SUCCESS" or data.get("result_code") != "SUCCESS":
            logger.warning(f"微信支付业务失败: {data.get('err_code_des')}")
            return PlainTextResponse(
                '<xml><return_code><![CDATA[SUCCESS]]></return_code></xml>'
            )

        # 获取关键参数
        out_trade_no = data.get("out_trade_no")
        trade_no = data.get("transaction_id")
        total_fee = int(data.get("total_fee", 0))

        # 查找订单
        order, order_type = _load_payable_order(db, out_trade_no)
        if not order:
            logger.warning(f"订单不存在: {out_trade_no}")
            return PlainTextResponse(
                '<xml><return_code><![CDATA[SUCCESS]]></return_code></xml>'
            )

        # 检查订单状态
        if order.status != "pending":
            logger.info(f"订单已处理: {out_trade_no}")
            return PlainTextResponse(
                '<xml><return_code><![CDATA[SUCCESS]]></return_code></xml>'
            )

        # 验证交易参数
        if not trade_no:
            logger.error(f"微信支付通知缺少交易号: {out_trade_no}")
            return PlainTextResponse(
                '<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[缺少交易号]]></return_msg></xml>'
            )

        order_amount = int((Decimal(str(order.pay_amount)) * Decimal("100")).quantize(Decimal("1")))
        if total_fee != order_amount:
            logger.error(f"金额不匹配: order={order_amount}, notify={total_fee}")
            return PlainTextResponse(
                '<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[金额不匹配]]></return_msg></xml>'
            )

        # 更新订单状态
        if order_type == "recharge":
            _mark_recharge_paid(order, "wechat", trade_no, db)
            logger.info(f"充值订单支付成功: {out_trade_no}")
        elif order_type == "membership":
            _mark_membership_paid(order, "wechat", trade_no, db)
            logger.info(f"会员订单支付成功: {out_trade_no}")
        else:
            _apply_model_fields(order, _payment_fields("wechat", trade_no))
            order.status = "paid"

            # 发送通知
            notification = Notification(
                user_id=order.user_id,
                notify_type="system",
                target_type="order",
                target_id=order.id,
                title="支付成功",
                content=f"您的订单 {order.order_no} 已支付成功，金额 ¥{total_fee / 100:.2f}"
            )
            db.add(notification)

        db.commit()
        logger.info(f"订单支付成功: {out_trade_no}")

        # WebSocket通知
        try:
            from app.websocket import manager
            import asyncio
            asyncio.create_task(
                manager.send_order_update(order.user_id, order.id, "paid", {
                    "order_no": order.order_no,
                    "amount": str(total_fee / 100)
                })
            )
        except Exception as e:
            logger.warning(f"WebSocket通知发送失败(微信): {str(e)}")

        return PlainTextResponse(
            '<xml><return_code><![CDATA[SUCCESS]]></return_code></xml>'
        )

    except Exception as e:
        logger.error(f"处理微信支付通知失败: {str(e)}")
        return PlainTextResponse(
            '<xml><return_code><![CDATA[FAIL]]></return_code><return_msg><![CDATA[系统错误]]></return_msg></xml>'
        )


@router.get("/status/{order_no}", summary="查询支付状态")
async def query_payment_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    查询订单支付状态

    前端可以轮询此接口获取支付结果
    """
    order = db.query(Order).filter(
        Order.order_no == order_no,
        Order.user_id == current_user.id
    ).first()
    if not order:
        order = db.query(PointsRechargeOrder).filter(
            PointsRechargeOrder.order_no == order_no,
            PointsRechargeOrder.user_id == current_user.id,
        ).first()
    if not order:
        order = db.query(MembershipOrder).filter(
            MembershipOrder.order_no == order_no,
            MembershipOrder.user_id == current_user.id,
        ).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    result = {
        "order_no": order.order_no,
        "status": order.status,
        "pay_method": order.pay_method,
        "pay_amount": float(order.pay_amount),
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "credited_at": order.credited_at.isoformat() if hasattr(order, "credited_at") and order.credited_at else None,
        "fulfilled_at": order.fulfilled_at.isoformat() if hasattr(order, "fulfilled_at") and order.fulfilled_at else None,
    }

    # 如果订单仍待支付，尝试主动查询支付平台
    if order.status == "pending" and order.pay_method:
        try:
            query_result = await payment_service.query_payment(
                order_no,
                order.pay_method
            )

            if query_result.get("success") and query_result.get("status") in ["TRADE_SUCCESS", "SUCCESS"]:
                trade_no = query_result.get("trade_no", "")
                amount = str(query_result.get("amount", ""))
                if trade_no and _amount_matches(order.pay_amount, amount):
                    if isinstance(order, PointsRechargeOrder):
                        _mark_recharge_paid(order, order.pay_method, trade_no, db)
                    elif isinstance(order, MembershipOrder):
                        _mark_membership_paid(order, order.pay_method, trade_no, db)
                    else:
                        order.status = "paid"
                        _apply_model_fields(order, _payment_fields(order.pay_method, trade_no))
                    db.commit()

                    result["status"] = "paid"
                    result["paid_at"] = order.paid_at.isoformat() if getattr(order, "paid_at", None) else None
                    result["credited_at"] = order.credited_at.isoformat() if hasattr(order, "credited_at") and order.credited_at else None
                    result["fulfilled_at"] = order.fulfilled_at.isoformat() if hasattr(order, "fulfilled_at") and order.fulfilled_at else None
                else:
                    logger.warning(f"主动查询支付结果不完整: order_no={order_no}, trade_no={trade_no}, amount={amount}")

        except Exception as e:
            logger.warning(f"主动查询支付状态失败: {str(e)}")

    return {"code": 200, "message": "success", "data": result}


@router.post("/refund/notify/alipay", summary="支付宝退款通知")
async def alipay_refund_notify(
    request: Request,
    db: Session = Depends(get_db)
):
    """处理支付宝退款通知"""
    try:
        form_data = await request.form()
        params = dict(form_data)

        logger.info(f"收到支付宝退款通知: {params}")

        # 验签
        alipay = AlipayService()
        if not alipay.verify_notify(params.copy()):
            return PlainTextResponse("fail")

        # 处理退款结果
        out_trade_no = params.get("out_trade_no")
        out_refund_no = params.get("out_request_no")
        refund_status = params.get("refund_status")

        if refund_status == "REFUND_SUCCESS":
            from app.models.shop import RefundRequest

            refund_query = db.query(RefundRequest).join(Order, RefundRequest.order_id == Order.id)
            if out_refund_no:
                refund_query = refund_query.filter(RefundRequest.refund_no == out_refund_no)
            elif out_trade_no:
                refund_query = refund_query.filter(Order.order_no == out_trade_no)
            else:
                logger.error("支付宝退款通知缺少订单号和退款单号")
                return PlainTextResponse("fail")

            refund = refund_query.order_by(RefundRequest.created_at.desc()).first()

            if refund:
                refund.status = "completed"
                refund.completed_at = datetime.now()
                refund.actual_refund = refund.refund_amount
                db.commit()

        return PlainTextResponse("success")

    except Exception as e:
        logger.error(f"处理退款通知失败: {str(e)}")
        return PlainTextResponse("fail")
