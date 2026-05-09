"""
PetPal - 测试配置文件

包含pytest fixtures和公共测试工具
"""
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 单测必须用本地 SQLite 内存库，避免命中真实 .env 配置的 MySQL
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
os.environ.setdefault("SECRET_KEY", "test-app-secret")
os.environ.setdefault("APP_ENV", "development")

# SQLite 对 BigInteger 不 autoincrement —— 编译为 INTEGER 让单测可用
from sqlalchemy.ext.compiler import compiles  # noqa: E402
from sqlalchemy.types import BigInteger as _BI  # noqa: E402


@compiles(_BI, "sqlite")
def _bigint_to_integer_on_sqlite(element, compiler, **kw):
    return "INTEGER"


@pytest.fixture
def db_session():
    """每个测试一个全新的 in-memory SQLite session，自动建表 + 拆毁。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    # 触发所有 model 注册到 Base.metadata
    import app.models  # noqa: F401

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def seed_user(db_session):
    """插入一个最小可用的 user，返回其 id。"""
    from app.models.user import User
    u = User(
        phone=f"139{abs(hash('petpal-test')) % 100000000:08d}",
        nickname="测试主人",
        password="test-hash",
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def seed_pet_avatar(db_session, seed_user):
    """给 seed_user 插入一只 pet + 对应的 PetAvatar。"""
    from app.models.pet import Pet
    from app.models.avatar import PetAvatar
    pet = Pet(owner_id=seed_user.id, name="豆包", pet_type="cat")
    db_session.add(pet)
    db_session.flush()
    avatar = PetAvatar(
        pet_id=pet.id, user_id=seed_user.id,
        speaking_style="cute",
        persona={"name": "豆包", "first_person_intro": "我是豆包"},
    )
    db_session.add(avatar)
    db_session.commit()
    return avatar


@pytest.fixture
def sample_image_bytes():
    """生成测试用的 PNG 图片字节（16x16，避开 validator 的"过小"过滤）"""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000100000001008060000001ff3ff61"
        "0000001d49444154789c63fc7f22e53f0305808912cda3068c1a306ac06032000018"
        "bc034a384102a10000000049454e44ae426082"
    )


@pytest.fixture
def sample_jpeg_bytes():
    """生成测试用的JPEG图片字节"""
    # JPEG文件头
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46,
        0x49, 0x46, 0x00, 0x01, 0x01, 0x00, 0x00, 0x01,
        0x00, 0x01, 0x00, 0x00
    ])


@pytest.fixture
def malicious_file_bytes():
    """生成包含可疑内容的文件字节"""
    return b'<script>alert("XSS")</script>'


@pytest.fixture
def sql_injection_samples():
    """SQL注入测试样本"""
    return [
        "'; DROP TABLE users; --",
        "1' OR '1'='1",
        "admin'--",
        "1; SELECT * FROM users",
        "' UNION SELECT * FROM passwords --",
        "1' AND 1=1 --",
        "'; EXEC xp_cmdshell('dir'); --",
        "1 OR 1=1",
        "' OR ''='",
    ]


@pytest.fixture
def xss_samples():
    """XSS攻击测试样本"""
    return [
        '<script>alert("XSS")</script>',
        '<img src="x" onerror="alert(1)">',
        '<svg onload="alert(1)">',
        'javascript:alert(1)',
        '<a href="javascript:alert(1)">Click</a>',
        '<div onclick="alert(1)">Test</div>',
        '"><script>alert(1)</script>',
        '<iframe src="javascript:alert(1)">',
    ]


@pytest.fixture
def safe_text_samples():
    """安全文本测试样本"""
    return [
        "Hello World",
        "这是一段中文文本",
        "User's input with apostrophe",
        "Email: test@example.com",
        "Price: $19.99",
        "100% satisfaction guaranteed",
    ]
