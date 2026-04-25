"""
PetPal - 会员API
"""
import time
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.membership import MembershipOrder
from app.models.user import User
from app.services.membership import MEMBERSHIP_PLANS, fulfill_membership_order, list_membership_plans
from app.services.payment_service import payment_service
from app.utils.deps import get_current_user
from app.utils.response import success

router = APIRouter()


class MembershipOrderRequest(BaseModel):
    """创建会员订单请求"""
    plan_code: str


class PayMembershipOrderRequest(BaseModel):
    """支付会员订单请求"""
    pay_type: str = "wechat"


def _is_local_development() -> bool:
    return settings.debug and settings.app_env == "development" and settings.app_base_url.startswith("http://localhost")


@router.get("/plans", summary="获取会员套餐")
async def get_membership_plans():
    """获取会员套餐列表"""
    return success(data=list_membership_plans())


@router.post("/orders", summary="创建会员订单")
async def create_membership_order(
    request: MembershipOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建会员订单"""
    plan = MEMBERSHIP_PLANS.get(request.plan_code)
    if not plan:
        raise HTTPException(status_code=400, detail="会员套餐不存在")

    order_no = f"MBR{int(time.time() * 1000)}{current_user.id}"
    order = MembershipOrder(
        order_no=order_no,
        user_id=current_user.id,
        plan_code=request.plan_code,
        plan_name=plan["name"],
        member_level=plan["member_level"],
        duration_days=plan["duration_days"],
        amount=plan["amount"],
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return success(data=order.to_dict(), message="创建会员订单成功")


@router.post("/orders/{order_id}/pay", summary="支付会员订单")
async def pay_membership_order(
    order_id: int,
    request: PayMembershipOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """支付会员订单"""
    if request.pay_type not in {"wechat", "alipay"}:
        raise HTTPException(status_code=400, detail="会员购买仅支持现金支付")

    order = db.query(MembershipOrder).filter(
        MembershipOrder.id == order_id,
        MembershipOrder.user_id == current_user.id,
        MembershipOrder.status == "pending",
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="会员订单不存在或状态异常")

    payment_result = await payment_service.create_payment(
        order_no=order.order_no,
        amount=Decimal(str(order.amount)),
        subject=f"PetPal会员-{order.plan_name}",
        payment_method=request.pay_type,
        client_type="h5",
        user_id=current_user.id,
        extra_data={"membership_order_id": order.id},
    )
    if not payment_result.success:
        raise HTTPException(status_code=400, detail=payment_result.error_message or "创建支付失败")

    order.pay_method = request.pay_type

    is_mock_payment = request.pay_type in {"alipay", "wechat"} and _is_local_development()
    if is_mock_payment:
        order.status = "paid"
        order.paid_at = datetime.now()
        order.trade_no = f"MOCK{int(time.time())}{current_user.id}"
        fulfill_membership_order(order, db)

    db.commit()
    db.refresh(order)

    return success(data={
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "pay_amount": float(order.amount),
        "pay_type": request.pay_type,
        "pay_data": payment_result.pay_data if payment_result else None,
        "trade_no": order.trade_no or (payment_result.trade_no if payment_result else ""),
        "is_mock_payment": is_mock_payment,
        "fulfilled_at": order.fulfilled_at.isoformat() if order.fulfilled_at else None,
        "member_level": current_user.member_level,
        "member_expire_at": current_user.member_expire_at.isoformat() if current_user.member_expire_at else None,
    }, message="支付成功" if order.status == "paid" else "请完成支付")


@router.get("/orders/{order_no}", summary="查询会员订单状态")
async def get_membership_order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询会员订单状态"""
    order = db.query(MembershipOrder).filter(
        MembershipOrder.order_no == order_no,
        MembershipOrder.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="会员订单不存在")

    if order.status == "pending" and order.pay_method:
        try:
            query_result = await payment_service.query_payment(order.order_no, order.pay_method)
            if query_result.get("success") and query_result.get("status") in ["TRADE_SUCCESS", "TRADE_FINISHED", "SUCCESS"]:
                trade_no = query_result.get("trade_no", "")
                amount = str(query_result.get("amount", ""))
                expected_cents = int((Decimal(str(order.amount)) * Decimal("100")).quantize(Decimal("1")))
                actual_cents = int((Decimal(amount) * Decimal("100")).quantize(Decimal("1"))) if amount else -1
                if trade_no and actual_cents == expected_cents:
                    order.trade_no = trade_no
                    order.paid_at = datetime.now()
                    fulfill_membership_order(order, db)
                    db.commit()
                    db.refresh(order)
        except Exception as exc:
            logger.warning(f"主动查询会员订单支付状态失败: {exc}")

    data = order.to_dict()
    data["member_expire_at"] = current_user.member_expire_at.isoformat() if current_user.member_expire_at else None
    return success(data=data)
