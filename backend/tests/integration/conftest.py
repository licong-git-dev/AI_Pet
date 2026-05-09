"""
PetPal · 集成测试公共 fixtures

把 FastAPI app 的 SQLAlchemy 依赖切到内存 SQLite，
然后用 TestClient 驱动真实路由 + 中间件 + 鉴权。
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import BigInteger as _BI

# 必须在 import app 前设
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-integration")
os.environ.setdefault("SECRET_KEY", "test-app-secret-integration")
os.environ.setdefault("APP_ENV", "development")
# 不让 prometheus instrumentator 在测试里发出 noisy 日志
os.environ.setdefault("DEBUG", "false")


@compiles(_BI, "sqlite")
def _bigint_to_integer_on_sqlite(element, compiler, **kw):
    return "INTEGER"


@pytest.fixture
def integration_app():
    """
    一份全新的 FastAPI app + 内存 SQLite + 内存 metadata。
    每个 test 独立一份，互不影响。
    """
    # 让 prometheus 注册表在每次 import 时不重复，import 之前清掉
    try:
        from prometheus_client import REGISTRY, CollectorRegistry  # noqa
        for c in list(REGISTRY._collector_to_names.keys()):
            try: REGISTRY.unregister(c)
            except Exception: pass
    except Exception:
        pass

    # 新 engine + Base
    # 关键：StaticPool 让所有 session 共享同一条 :memory: 连接，否则每次拿连接都是新 DB
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.database import Base
    import app.models  # 注册所有 model
    Base.metadata.create_all(bind=engine)

    # 替换 app.database 的全局 engine + SessionLocal
    # 中间件 / Celery / 直接 import SessionLocal 的代码都会走我们的内存库
    import app.database as _app_db
    _orig_engine, _orig_session = _app_db.engine, _app_db.SessionLocal
    _app_db.engine = engine
    _app_db.SessionLocal = SessionLocal

    # 覆盖 get_db 依赖让它用我们的内存 session
    from app.main import app
    from app.database import get_db

    def _override_get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield app, SessionLocal
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    # 还原 app.database 全局
    _app_db.engine = _orig_engine
    _app_db.SessionLocal = _orig_session


@pytest.fixture
def client(integration_app):
    app, _ = integration_app
    return TestClient(app)


@pytest.fixture
def db_factory(integration_app):
    _, SessionLocal = integration_app
    return SessionLocal


@pytest.fixture
def seeded(db_factory):
    """造一个 user + pet + avatar，并返回 (user_id, pet_id, avatar_id)。"""
    from app.models.user import User
    from app.models.pet import Pet
    from app.models.avatar import PetAvatar
    s = db_factory()
    try:
        u = User(phone="13900000001", nickname="整合测试主人", password="x")
        s.add(u); s.flush()
        p = Pet(owner_id=u.id, name="豆包", pet_type="cat")
        s.add(p); s.flush()
        a = PetAvatar(pet_id=p.id, user_id=u.id, speaking_style="cute",
                      persona={"name": "豆包"})
        s.add(a); s.commit()
        return {"user_id": u.id, "pet_id": p.id, "avatar_id": a.id}
    finally:
        s.close()


@pytest.fixture
def auth_headers(seeded):
    """生成一个属于 seeded user 的有效 JWT header。"""
    from app.utils.security import create_access_token
    token = create_access_token(data={"sub": str(seeded["user_id"])})
    return {"Authorization": f"Bearer {token}"}
