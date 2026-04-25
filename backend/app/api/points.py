"""
PetPal - 积分API
"""
import secrets
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session
from loguru import logger

from app.config import settings
from app.database import get_db
from app.models.points import PointsExchange, PointsProduct, PointsRecord, PointsRechargeOrder
from app.models.user import User
from app.services.payment_service import payment_service
from app.services.points_recharge import RECHARGE_PACKAGES, fulfill_recharge_order, list_recharge_packages
from app.utils.deps import get_current_user
from app.utils.response import page_response, success

router = APIRouter()


# Redis客户端（懒加载）
_redis_client = None


def _get_redis():
    """获取Redis客户端"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis不可用: {e}")
        return None


# 内存存储（Redis不可用时的降级方案）
_memory_checkin = {}


def _is_local_development() -> bool:
    return settings.debug and settings.app_env == "development" and settings.app_base_url.startswith("http://localhost")


class RechargeOrderRequest(BaseModel):
    """创建积分充值订单请求"""
    package_code: str


class PayRechargeOrderRequest(BaseModel):
    """支付积分充值订单请求"""
    pay_type: str = "wechat"


def _has_required_member_level(user: User, required_level: int) -> bool:
    """检查用户是否满足会员等级要求。"""
    if required_level <= 0:
        return True

    if user.member_level < required_level or not user.member_expire_at:
        return False

    return user.member_expire_at > datetime.now()


def generate_coupon_code(prefix: str = "PP") -> str:
    """生成优惠券码

    Args:
        prefix: 优惠券码前缀

    Returns:
        格式如: PP-XXXX-XXXX-XXXX
    """
    code_parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"{prefix}-{'-'.join(code_parts)}"


class ExchangeRequest(BaseModel):
    """兑换请求"""
    product_id: int
    quantity: int = 1
    address_id: Optional[int] = None


@router.get("/balance", summary="获取积分余额")
async def get_points_balance(current_user: User = Depends(get_current_user)):
    """获取当前用户积分余额"""
    return success(data={
        "balance": current_user.points,
        "member_level": current_user.member_level
    })


@router.get("/records", summary="获取积分记录")
async def get_points_records(
    source_type: str = Query(None, description="来源类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取积分变动记录"""
    query = db.query(PointsRecord).filter(PointsRecord.user_id == current_user.id)

    if source_type:
        query = query.filter(PointsRecord.source_type == source_type)

    query = query.order_by(desc(PointsRecord.created_at))

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[r.to_dict() for r in records],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/products", summary="获取积分商品列表")
async def get_points_products(
    category: str = Query(None, description="分类筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """获取可兑换的积分商品"""
    query = db.query(PointsProduct).filter(
        PointsProduct.status == 1,
        PointsProduct.stock > 0
    )

    if category:
        query = query.filter(PointsProduct.category == category)

    query = query.order_by(desc(PointsProduct.is_hot), desc(PointsProduct.created_at))

    total = query.count()
    products = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[p.to_dict() for p in products],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/products/{product_id}", summary="获取积分商品详情")
async def get_points_product(product_id: int, db: Session = Depends(get_db)):
    """获取积分商品详情"""
    product = db.query(PointsProduct).filter(
        PointsProduct.id == product_id,
        PointsProduct.status == 1
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    return success(data=product.to_dict())


@router.get("/recharge/packages", summary="获取积分充值套餐")
async def get_recharge_packages():
    """获取积分充值套餐列表"""
    return success(data=list_recharge_packages())


@router.post("/recharge/orders", summary="创建积分充值订单")
async def create_recharge_order(
    request: RechargeOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建积分充值订单"""
    package = RECHARGE_PACKAGES.get(request.package_code)
    if not package:
        raise HTTPException(status_code=400, detail="充值套餐不存在")

    order_no = f"RCG{int(time.time() * 1000)}{current_user.id}"
    order = PointsRechargeOrder(
        order_no=order_no,
        user_id=current_user.id,
        package_code=request.package_code,
        package_name=package["name"],
        points=package["points"],
        bonus_points=package["bonus_points"],
        amount=package["amount"],
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    return success(data=order.to_dict(), message="创建充值订单成功")


@router.post("/recharge/orders/{order_id}/pay", summary="支付积分充值订单")
async def pay_recharge_order(
    order_id: int,
    request: PayRechargeOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """支付积分充值订单"""
    if request.pay_type not in {"wechat", "alipay"}:
        raise HTTPException(status_code=400, detail="积分充值仅支持现金支付")

    order = db.query(PointsRechargeOrder).filter(
        PointsRechargeOrder.id == order_id,
        PointsRechargeOrder.user_id == current_user.id,
        PointsRechargeOrder.status == "pending",
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="充值订单不存在或状态异常")

    payment_result = await payment_service.create_payment(
        order_no=order.order_no,
        amount=Decimal(str(order.amount)),
        subject=f"PetPal积分充值-{order.package_name}",
        payment_method=request.pay_type,
        client_type="h5",
        user_id=current_user.id,
        extra_data={"recharge_order_id": order.id},
    )
    if not payment_result.success:
        raise HTTPException(status_code=400, detail=payment_result.error_message or "创建支付失败")

    order.pay_method = request.pay_type

    is_mock_payment = request.pay_type in {"alipay", "wechat"} and _is_local_development()
    if is_mock_payment:
        order.status = "paid"
        order.paid_at = datetime.now()
        order.trade_no = f"MOCK{int(time.time())}{current_user.id}"
        fulfill_recharge_order(order, db)

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
        "is_mock_payment": request.pay_type in {"alipay", "wechat"} and _is_local_development(),
        "credited_at": order.credited_at.isoformat() if order.credited_at else None,
    }, message="支付成功" if order.status == "paid" else "请完成支付")


@router.get("/recharge/orders/{order_no}", summary="查询积分充值订单状态")
async def get_recharge_order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询积分充值订单状态"""
    order = db.query(PointsRechargeOrder).filter(
        PointsRechargeOrder.order_no == order_no,
        PointsRechargeOrder.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="充值订单不存在")

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
                    fulfill_recharge_order(order, db)
                    db.commit()
                    db.refresh(order)
        except Exception as exc:
            logger.warning(f"主动查询充值订单支付状态失败: {exc}")

    return success(data=order.to_dict())


@router.post("/exchange", summary="积分兑换")
async def exchange_points(
    request: ExchangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """使用积分兑换商品

    支持三种商品类型：
    - coupon: 优惠券（自动生成优惠券码）
    - physical: 实物商品（需要收货地址）
    - virtual: 虚拟商品
    """
    product_id = request.product_id
    quantity = request.quantity
    address_id = request.address_id

    product = db.query(PointsProduct).filter(
        PointsProduct.id == product_id,
        PointsProduct.status == 1
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    # 检查时间有效性
    now = datetime.now()
    if product.start_time and now < product.start_time:
        raise HTTPException(status_code=400, detail="兑换活动尚未开始")
    if product.end_time and now > product.end_time:
        raise HTTPException(status_code=400, detail="兑换活动已结束")

    if product.stock < quantity:
        raise HTTPException(status_code=400, detail="库存不足")

    total_points = product.points_price * quantity

    if current_user.points < total_points:
        raise HTTPException(status_code=400, detail="积分不足")

    # 检查会员等级限制
    if product.member_level_required and not _has_required_member_level(current_user, product.member_level_required):
        raise HTTPException(status_code=400, detail=f"需要有效会员等级{product.member_level_required}以上")

    # 检查用户兑换次数限制
    if product.limit_per_user > 0:
        user_exchange_count = db.query(PointsExchange).filter(
            PointsExchange.user_id == current_user.id,
            PointsExchange.product_id == product_id,
            PointsExchange.status != "cancelled"
        ).count()
        if user_exchange_count + quantity > product.limit_per_user:
            raise HTTPException(
                status_code=400,
                detail=f"每人限兑{product.limit_per_user}件，您已兑换{user_exchange_count}件"
            )

    # 检查实物商品需要收货地址
    receiver_name = None
    receiver_phone = None
    receiver_address = None

    if product.product_type == "physical":
        if not address_id:
            raise HTTPException(status_code=400, detail="实物商品需要选择收货地址")

        # 查询地址信息
        from app.models.shop import UserAddress
        address = db.query(UserAddress).filter(
            UserAddress.id == address_id,
            UserAddress.user_id == current_user.id
        ).first()

        if not address:
            raise HTTPException(status_code=400, detail="收货地址不存在")

        receiver_name = address.receiver_name
        receiver_phone = address.receiver_phone
        receiver_address = f"{address.province}{address.city}{address.district}{address.detail}"

    # 生成优惠券码（如果是优惠券类型）
    coupon_code = None
    coupon_expire_at = None

    if product.product_type == "coupon":
        coupon_code = generate_coupon_code()
        # 优惠券有效期30天
        coupon_expire_at = now + timedelta(days=30)

    # 创建兑换记录
    exchange = PointsExchange(
        user_id=current_user.id,
        product_id=product_id,
        product_name=product.name,
        points_cost=total_points,
        quantity=quantity,
        address_id=address_id,
        receiver_name=receiver_name,
        receiver_phone=receiver_phone,
        receiver_address=receiver_address,
        coupon_code=coupon_code,
        coupon_expire_at=coupon_expire_at,
        status="pending" if product.product_type == "physical" else "completed"
    )
    db.add(exchange)
    db.flush()  # 获取exchange.id

    # 扣除积分并记录
    points_record = PointsRecord(
        user_id=current_user.id,
        points=-total_points,
        balance=current_user.points - total_points,
        source_type="exchange",
        source_id=exchange.id,
        description=f"兑换{product.name}"
    )
    current_user.points -= total_points
    db.add(points_record)

    # 扣减库存并增加兑换数量
    product.stock -= quantity
    product.exchange_count += quantity

    db.commit()
    db.refresh(exchange)

    logger.info(
        f"积分兑换成功: user_id={current_user.id}, product_id={product_id}, "
        f"points_cost={total_points}, coupon_code={coupon_code}"
    )

    # 构建响应
    response_data = {
        "exchange_id": exchange.id,
        "points_cost": total_points,
        "remaining_points": current_user.points,
        "status": exchange.status
    }

    # 如果是优惠券，返回优惠券信息
    if coupon_code:
        response_data["coupon"] = {
            "code": coupon_code,
            "value": product.coupon_value,
            "min_amount": product.coupon_min_amount,
            "expire_at": coupon_expire_at.isoformat()
        }

    return success(data=response_data, message="兑换成功")


@router.get("/exchanges", summary="获取兑换记录")
async def get_exchanges(
    status: str = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的积分兑换记录"""
    query = db.query(PointsExchange).filter(PointsExchange.user_id == current_user.id)

    if status:
        query = query.filter(PointsExchange.status == status)

    query = query.order_by(desc(PointsExchange.created_at))

    total = query.count()
    exchanges = query.offset((page - 1) * page_size).limit(page_size).all()

    return page_response(
        data=[e.to_dict() for e in exchanges],
        page=page,
        page_size=page_size,
        total=total
    )


@router.get("/exchanges/{exchange_id}", summary="获取兑换详情")
async def get_exchange(
    exchange_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取兑换记录详情"""
    exchange = db.query(PointsExchange).filter(
        PointsExchange.id == exchange_id,
        PointsExchange.user_id == current_user.id
    ).first()

    if not exchange:
        raise HTTPException(status_code=404, detail="兑换记录不存在")

    return success(data=exchange.to_dict())


@router.post("/checkin", summary="每日签到")
async def daily_checkin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """每日签到获取积分

    签到规则：
    - 基础积分：5分
    - 连续签到奖励：每天额外+2分（最多+12分）
    - 连续签到7天可获得最高17分
    """
    redis_client = _get_redis()

    # 检查今日是否已签到
    today = datetime.now().strftime("%Y-%m-%d")
    checkin_key = f"checkin:{current_user.id}:{today}"

    if redis_client:
        if redis_client.exists(checkin_key):
            raise HTTPException(status_code=400, detail="今日已签到")

        # 获取连续签到天数
        streak_key = f"checkin_streak:{current_user.id}"
        yesterday = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) -
                     timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_key = f"checkin:{current_user.id}:{yesterday}"

        if redis_client.exists(yesterday_key):
            streak = int(redis_client.get(streak_key) or 0) + 1
        else:
            streak = 1

        # 记录签到
        redis_client.setex(checkin_key, 48 * 3600, "1")  # 48小时过期
        redis_client.setex(streak_key, 48 * 3600, str(streak))
    else:
        # 使用内存存储作为降级方案
        if checkin_key in _memory_checkin:
            raise HTTPException(status_code=400, detail="今日已签到")

        streak_key = f"checkin_streak:{current_user.id}"
        yesterday = (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) -
                     timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_key = f"checkin:{current_user.id}:{yesterday}"

        if yesterday_key in _memory_checkin:
            streak = _memory_checkin.get(streak_key, 0) + 1
        else:
            streak = 1

        _memory_checkin[checkin_key] = True
        _memory_checkin[streak_key] = streak

    # 计算签到积分（连续签到奖励）
    base_points = 2
    bonus_points = min(streak - 1, 6) * 1  # 最多额外6分
    total_points = base_points + bonus_points

    # 增加积分
    points_record = PointsRecord(
        user_id=current_user.id,
        points=total_points,
        balance=current_user.points + total_points,
        source_type="checkin",
        description=f"每日签到（连续{streak}天）"
    )
    current_user.points += total_points
    db.add(points_record)
    db.commit()

    logger.info(f"用户签到成功: user_id={current_user.id}, streak={streak}, points={total_points}")

    return success(data={
        "points_earned": total_points,
        "streak_days": streak,
        "total_points": current_user.points
    }, message=f"签到成功，获得{total_points}积分")


@router.get("/checkin/status", summary="获取签到状态")
async def get_checkin_status(
    current_user: User = Depends(get_current_user)
):
    """获取今日签到状态和连续签到天数"""
    redis_client = _get_redis()

    today = datetime.now().strftime("%Y-%m-%d")
    checkin_key = f"checkin:{current_user.id}:{today}"
    streak_key = f"checkin_streak:{current_user.id}"

    if redis_client:
        is_checked = redis_client.exists(checkin_key)
        streak = int(redis_client.get(streak_key) or 0)
    else:
        is_checked = checkin_key in _memory_checkin
        streak = _memory_checkin.get(streak_key, 0)

    # 计算明日可得积分
    if is_checked:
        next_reward = 2 + min(streak, 6) * 1  # 已签到，基于当前连续天数
    else:
        next_reward = 2 + min(streak, 6) * 1  # 未签到，今天签到可得

    return success(data={
        "is_checked_today": bool(is_checked),
        "streak_days": streak,
        "next_reward": next_reward
    })
