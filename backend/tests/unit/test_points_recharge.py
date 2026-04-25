import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models.points import PointsRechargeOrder, PointsRecord
from app.models.user import User
from app.services.points_recharge import fulfill_recharge_order, list_recharge_packages

points_module_path = Path(__file__).resolve().parents[2] / "app" / "api" / "points.py"
points_spec = importlib.util.spec_from_file_location("test_points_api_module", points_module_path)
points_module = importlib.util.module_from_spec(points_spec)
assert points_spec.loader is not None
points_spec.loader.exec_module(points_module)
PayRechargeOrderRequest = points_module.PayRechargeOrderRequest
_has_required_member_level = points_module._has_required_member_level
create_recharge_order = points_module.create_recharge_order
pay_recharge_order = points_module.pay_recharge_order


class QueryStub:
    def __init__(self, result):
        self.result = result

    def filter(self, *args):
        return self

    def first(self):
        return self.result


class RechargeDbStub:
    def __init__(self, user=None, order=None):
        self.user = user
        self.order = order
        self.added = []
        self.committed = False
        self.refreshed = []

    def query(self, model):
        if model is User:
            return QueryStub(self.user)
        if model is PointsRechargeOrder:
            return QueryStub(self.order)
        raise AssertionError(f"unexpected model query: {model}")

    def add(self, item):
        self.added.append(item)
        if isinstance(item, PointsRechargeOrder) and self.order is None:
            self.order = item

    def commit(self):
        self.committed = True

    def refresh(self, item):
        self.refreshed.append(item)
        if getattr(item, "id", None) is None:
            item.id = 101


@pytest.mark.asyncio
async def test_create_recharge_order_uses_static_package_config():
    current_user = User()
    current_user.id = 7
    current_user.points = 10
    db = RechargeDbStub()

    response = await create_recharge_order(
        request=SimpleNamespace(package_code="medium"),
        current_user=current_user,
        db=db,
    )

    assert response["code"] == 0
    assert response["data"]["package_code"] == "medium"
    assert response["data"]["total_points"] == 550
    assert response["data"]["status"] == "pending"
    assert isinstance(db.order, PointsRechargeOrder)
    assert db.order.package_name == "常用积分包"
    assert db.committed is True


@pytest.mark.asyncio
async def test_pay_recharge_order_rejects_balance_pay_type():
    current_user = User()
    current_user.id = 7
    current_user.points = 500

    order = PointsRechargeOrder()
    order.id = 12
    order.user_id = 7
    order.order_no = "RCG123"
    order.package_code = "small"
    order.package_name = "小额积分包"
    order.points = 100
    order.bonus_points = 0
    order.amount = 1.0
    order.status = "pending"
    order.credited_at = None

    db = RechargeDbStub(user=current_user, order=order)

    with pytest.raises(HTTPException) as exc:
        await pay_recharge_order(
            order_id=12,
            request=PayRechargeOrderRequest(pay_type="balance"),
            current_user=current_user,
            db=db,
        )

    assert exc.value.status_code == 400
    assert "仅支持现金支付" in exc.value.detail
    assert db.committed is False
    assert all(not isinstance(item, PointsRecord) for item in db.added)


def test_fulfill_recharge_order_is_idempotent():
    user = User()
    user.id = 9
    user.points = 20

    order = PointsRechargeOrder()
    order.id = 3
    order.user_id = 9
    order.package_name = "超值积分包"
    order.points = 1000
    order.bonus_points = 150
    order.status = "pending"
    order.credited_at = None

    db = RechargeDbStub(user=user, order=order)

    first = fulfill_recharge_order(order, db)
    second = fulfill_recharge_order(order, db)

    records = [item for item in db.added if isinstance(item, PointsRecord)]

    assert first is True
    assert second is False
    assert user.points == 1170
    assert len(records) == 1
    assert records[0].points == 1150
    assert records[0].balance == 1170


def test_list_recharge_packages_exposes_total_points():
    packages = list_recharge_packages()

    assert [item["code"] for item in packages] == ["small", "medium", "large"]
    assert packages[1]["total_points"] == 550


def test_has_required_member_level_requires_unexpired_membership():
    user = User()
    user.member_level = 1
    user.member_expire_at = datetime.now() - timedelta(minutes=1)

    assert _has_required_member_level(user, 1) is False


def test_has_required_member_level_accepts_active_membership():
    user = User()
    user.member_level = 1
    user.member_expire_at = datetime.now() + timedelta(days=1)

    assert _has_required_member_level(user, 1) is True


@pytest.mark.asyncio
async def test_pay_recharge_order_rejects_unknown_pay_type():
    current_user = User()
    current_user.id = 7
    order = PointsRechargeOrder()
    order.id = 1
    order.user_id = 7
    order.status = "pending"
    db = RechargeDbStub(user=current_user, order=order)

    with pytest.raises(HTTPException) as exc:
        await pay_recharge_order(
            order_id=1,
            request=PayRechargeOrderRequest(pay_type="cash"),
            current_user=current_user,
            db=db,
        )

    assert exc.value.status_code == 400
