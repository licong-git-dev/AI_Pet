"""
PetPal - Alembic 迁移环境配置

此文件配置Alembic如何连接数据库和检测模型变化。
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 导入应用配置
from app.config import settings

# 导入Base和所有模型（确保模型被加载）
from app.database import Base
from app.models import *  # noqa: F401, F403

# Alembic Config对象
config = context.config

# 如果存在alembic.ini的logging配置，则设置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy MetaData对象（用于自动迁移生成）
target_metadata = Base.metadata

# 从应用配置获取数据库URL
def get_url():
    """获取数据库连接URL"""
    return settings.database_url


def run_migrations_offline() -> None:
    """以'离线'模式运行迁移。

    这种模式下，只需配置URL即可，无需创建Engine实例。
    通过调用context.execute()生成SQL语句到脚本输出。
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 比较类型变化
        compare_type=True,
        # 比较服务器默认值
        compare_server_default=True,
        # 渲染SQL as批量操作（提高性能）
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以'在线'模式运行迁移。

    在这种模式下，需要创建Engine实例并关联connection。
    """
    # 获取配置并设置数据库URL
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # 比较类型变化
            compare_type=True,
            # 比较服务器默认值
            compare_server_default=True,
            # SQLite需要批量模式处理约束
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
