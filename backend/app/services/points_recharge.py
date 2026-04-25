"""
PetPal - 积分充值服务
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.points import PointsRecord, PointsRechargeOrder
from app.models.user import User

RECHARGE_PACKAGES = {
    "small": {"name": "小额积分包", "points": 100, "bonus_points": 0, "amount": 1.0},
    "medium": {"name": "常用积分包", "points": 500, "bonus_points": 50, "amount": 5.0},
    "large": {"name": "超值积分包", "points": 1000, "bonus_points": 150, "amount": 10.0},
}


def list_recharge_packages() -> list[dict]:
    """获取可购买的积分充值套餐。"""
    return [
        {
            "code": code,
            "name": package["name"],
            "points": package["points"],
            "bonus_points": package["bonus_points"],
            "total_points": package["points"] + package["bonus_points"],
            "amount": package["amount"],
        }
        for code, package in RECHARGE_PACKAGES.items()
    ]


def fulfill_recharge_order(order: PointsRechargeOrder, db: Session) -> bool:
    """幂等发放充值积分，已发放时返回False。"""
    if order.credited_at is not None:
        return False

    user = db.query(User).filter(User.id == order.user_id).first()
    if not user:
        raise ValueError("用户不存在")

    total_points = order.points + order.bonus_points
    user.points += total_points
    order.credited_at = datetime.now()
    order.status = "paid"

    db.add(PointsRecord(
        user_id=order.user_id,
        points=total_points,
        balance=user.points,
        source_type="recharge",
        source_id=order.id,
        description=f"积分充值：{order.package_name}",
    ))
    return True
