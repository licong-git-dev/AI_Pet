import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.models.health import HealthRecord
from app.models.pet import Pet
from app.models.points import PointsRecord
from app.models.user import User
from app.schemas.health import HealthAnalysisRequest

health_module_path = Path(__file__).resolve().parents[2] / "app" / "api" / "health.py"
health_spec = importlib.util.spec_from_file_location("test_health_api_module", health_module_path)
health_module = importlib.util.module_from_spec(health_spec)
assert health_spec.loader is not None
health_spec.loader.exec_module(health_module)
analyze_health = health_module.analyze_health


class QueryStub:
    def __init__(self, result):
        self.result = result

    def filter(self, *args):
        return self

    def first(self):
        return self.result


class DbStub:
    def __init__(self, pet):
        self.pet = pet
        self.added = []
        self.committed = False
        self.refreshed = []

    def query(self, model):
        assert model is Pet
        return QueryStub(self.pet)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.committed = True

    def refresh(self, item):
        self.refreshed.append(item)
        item.id = 123


def make_pet() -> Pet:
    pet = Pet()
    pet.id = 1
    pet.owner_id = 7
    pet.pet_type = "cat"
    pet.breed_name = "英短"
    return pet


def make_user(points: int, member_level: int = 0, member_expire_at=None) -> User:
    user = User()
    user.id = 7
    user.points = points
    user.member_level = member_level
    user.member_expire_at = member_expire_at
    return user


@pytest.mark.asyncio
async def test_analyze_health_rejects_user_with_insufficient_points(monkeypatch):
    db = DbStub(make_pet())
    user = make_user(4)
    request = HealthAnalysisRequest(pet_id=1, images=["https://example.com/cat.jpg"], description="眼睛发红")
    ai_called = False

    async def fake_analyze_pet_health(**kwargs):
        nonlocal ai_called
        ai_called = True
        return {}

    monkeypatch.setattr("app.services.ai_health.analyze_pet_health", fake_analyze_pet_health)

    with pytest.raises(HTTPException) as exc:
        await analyze_health(request, user, db)

    assert exc.value.status_code == 400
    assert "积分不足" in exc.value.detail
    assert ai_called is False


@pytest.mark.asyncio
async def test_analyze_health_creates_no_records_when_points_insufficient(monkeypatch):
    db = DbStub(make_pet())
    user = make_user(4)
    request = HealthAnalysisRequest(pet_id=1, images=["https://example.com/cat.jpg"], description="眼睛发红")

    async def fake_analyze_pet_health(**kwargs):
        return {"analysis": "不应调用"}

    monkeypatch.setattr("app.services.ai_health.analyze_pet_health", fake_analyze_pet_health)

    with pytest.raises(HTTPException):
        await analyze_health(request, user, db)

    assert db.added == []
    assert db.committed is False
    assert user.points == 4


@pytest.mark.asyncio
async def test_analyze_health_success_deducts_points_and_returns_data(monkeypatch):
    db = DbStub(make_pet())
    # 普通用户健康分析成本 20 分；初始 20 → 扣 20 → 余 0（与下面断言一致）
    user = make_user(20)
    request = HealthAnalysisRequest(pet_id=1, images=["https://example.com/cat.jpg"], description="眼睛发红")

    async def fake_analyze_pet_health(**kwargs):
        return {
            "analysis": "疑似轻微结膜刺激",
            "suggestions": "保持清洁并观察",
            "risk_level": "low",
            "possible_conditions": ["结膜刺激"],
            "recommended_actions": ["观察"],
        }

    monkeypatch.setattr("app.services.ai_health.analyze_pet_health", fake_analyze_pet_health)

    response = await analyze_health(request, user, db)

    health_record = next(item for item in db.added if isinstance(item, HealthRecord))
    points_record = next(item for item in db.added if isinstance(item, PointsRecord))

    assert user.points == 0
    assert points_record.points == -20
    assert points_record.balance == 0
    assert points_record.source_type == "health_analysis"
    assert health_record.user_id == 7
    assert health_record.ai_analysis == "疑似轻微结膜刺激"
    assert db.committed is True
    assert response["code"] == 0
    assert response["data"]["record_id"] == 123
    assert response["data"]["analysis"] == "疑似轻微结膜刺激"


@pytest.mark.asyncio
async def test_analyze_health_member_discount_uses_lower_points_cost(monkeypatch):
    db = DbStub(make_pet())
    user = make_user(
        15,
        member_level=1,
        member_expire_at=datetime.now() + timedelta(days=1),
    )
    request = HealthAnalysisRequest(pet_id=1, images=["https://example.com/cat.jpg"], description="眼睛发红")

    async def fake_analyze_pet_health(**kwargs):
        return {
            "analysis": "疑似轻微结膜刺激",
            "suggestions": "保持清洁并观察",
            "risk_level": "low",
            "possible_conditions": ["结膜刺激"],
            "recommended_actions": ["观察"],
        }

    monkeypatch.setattr("app.services.ai_health.analyze_pet_health", fake_analyze_pet_health)

    response = await analyze_health(request, user, db)

    points_record = next(item for item in db.added if isinstance(item, PointsRecord))

    assert user.points == 3
    assert points_record.points == -12
    assert points_record.balance == 3
    assert response["code"] == 0
