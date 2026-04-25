from datetime import datetime, timedelta

import pytest

from app.models.membership import MembershipOrder
from app.models.user import User
from app.services.membership import fulfill_membership_order, list_membership_plans


class QueryStub:
    def __init__(self, result):
        self.result = result

    def populate_existing(self):
        return self

    def filter(self, *args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.result


class MembershipDbStub:
    def __init__(self, order=None, user=None):
        self.order = order
        self.user = user
        self.expired = []

    def expire(self, obj):
        self.expired.append(obj)

    def query(self, model):
        if model is MembershipOrder:
            return QueryStub(self.order)
        if model is User:
            return QueryStub(self.user)
        raise AssertionError(f'unexpected model query: {model}')


def test_list_membership_plans_exposes_monthly_and_yearly_options():
    plans = list_membership_plans()

    assert [plan['code'] for plan in plans] == ['monthly_vip', 'yearly_vip']
    assert plans[0]['benefits'][0] == 'AI 健康分析 12 积分/次'
    assert plans[1]['member_level'] == 2
    assert plans[1]['duration_days'] == 365
    assert plans[1]['amount'] == 99.0


def test_fulfill_membership_order_extends_from_active_expire_time():
    current_expire_at = datetime.now() + timedelta(days=10)

    user = User()
    user.id = 8
    user.member_level = 1
    user.member_expire_at = current_expire_at

    order = MembershipOrder()
    order.id = 6
    order.user_id = 8
    order.member_level = 2
    order.duration_days = 365
    order.fulfilled_at = None
    order.status = 'pending'

    db = MembershipDbStub(order=order, user=user)

    fulfilled = fulfill_membership_order(order, db)

    assert fulfilled is True
    assert user.member_level == 2
    assert user.member_expire_at > current_expire_at + timedelta(days=364)
    assert order.status == 'paid'
    assert order.fulfilled_at is not None
    assert db.expired == [order]


def test_fulfill_membership_order_is_idempotent():
    user = User()
    user.id = 9
    user.member_level = 1
    user.member_expire_at = datetime.now() + timedelta(days=5)

    order = MembershipOrder()
    order.id = 7
    order.user_id = 9
    order.member_level = 1
    order.duration_days = 30
    order.fulfilled_at = datetime.now()
    order.status = 'paid'

    db = MembershipDbStub(order=order, user=user)

    fulfilled = fulfill_membership_order(order, db)

    assert fulfilled is False


def test_fulfill_membership_order_rejects_downgrade_while_higher_tier_active():
    user = User()
    user.id = 10
    user.member_level = 2
    user.member_expire_at = datetime.now() + timedelta(days=30)

    order = MembershipOrder()
    order.id = 8
    order.user_id = 10
    order.member_level = 1
    order.duration_days = 30
    order.fulfilled_at = None
    order.status = 'pending'

    db = MembershipDbStub(order=order, user=user)

    with pytest.raises(ValueError) as exc:
        fulfill_membership_order(order, db)

    assert '更高级会员生效中' in str(exc.value)
