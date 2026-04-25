"""
PetPal - 会员购买服务
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.middleware.rate_limit import invalidate_user_vip_cache
from app.models.membership import MembershipOrder
from app.models.user import User

MEMBERSHIP_PLANS = {
    "monthly_vip": {
        "name": "月度会员",
        "member_level": 1,
        "duration_days": 30,
        "amount": 9.9,
        "benefits": [
            "AI 健康分析 12 积分/次",
            "VIP 差异化限流",
            "会员专属积分商品",
        ],
    },
    "yearly_vip": {
        "name": "年度会员",
        "member_level": 2,
        "duration_days": 365,
        "amount": 99.0,
        "benefits": [
            "AI 健康分析 12 积分/次",
            "VIP 差异化限流",
            "会员专属积分商品",
            "年度套餐更划算",
        ],
    },
}


def list_membership_plans() -> list[dict]:
    """获取可购买的会员套餐。"""
    return [
        {
            "code": code,
            "name": plan["name"],
            "member_level": plan["member_level"],
            "duration_days": plan["duration_days"],
            "amount": plan["amount"],
            "benefits": plan["benefits"],
        }
        for code, plan in MEMBERSHIP_PLANS.items()
    ]


def fulfill_membership_order(order: MembershipOrder, db: Session) -> bool:
    """幂等开通会员，已开通时返回False。"""
    db.expire(order)
    locked_order = db.query(MembershipOrder).populate_existing().filter(
        MembershipOrder.id == order.id
    ).with_for_update().first()
    if not locked_order:
        raise ValueError("会员订单不存在")
    if locked_order.fulfilled_at is not None:
        return False

    user = db.query(User).filter(
        User.id == locked_order.user_id
    ).with_for_update().first()
    if not user:
        raise ValueError("用户不存在")

    now = datetime.now()
    current_expire_at = user.member_expire_at
    current_level = user.member_level or 0
    has_active_higher_level = (
        current_level > locked_order.member_level
        and current_expire_at is not None
        and current_expire_at > now
    )
    if has_active_higher_level:
        raise ValueError("当前已有更高级会员生效中，请到期后再购买低等级套餐")

    starts_at = current_expire_at if current_expire_at and current_expire_at > now else now

    user.member_level = max(current_level, locked_order.member_level)
    user.member_expire_at = starts_at + timedelta(days=locked_order.duration_days)
    locked_order.fulfilled_at = now
    locked_order.status = "paid"
    invalidate_user_vip_cache(locked_order.user_id)
    return True
