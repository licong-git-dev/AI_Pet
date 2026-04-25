"""
PetPal - 数据库连接模块
"""
from sqlalchemy import create_engine, BigInteger, Integer
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import event
from app.config import settings

# 创建数据库引擎
# SQLite不支持连接池参数
if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=settings.debug
    )

    # SQLite: 使用INTEGER代替BIGINT以支持AUTOINCREMENT
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=settings.debug
    )

# 创建Session工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


def get_db():
    """获取数据库Session依赖"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
