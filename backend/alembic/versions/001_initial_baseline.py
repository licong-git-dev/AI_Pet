"""Initial baseline migration - All existing tables

Revision ID: 001_initial
Revises:
Create Date: 2025-01-05

This is the initial baseline migration that represents all existing tables.
Use this as the starting point after the database has been created.

To mark existing database as migrated to this version:
    alembic stamp 001_initial
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    升级数据库到此版本

    注意: 此迁移文件为基线迁移，用于标记现有数据库状态。
    如果是全新数据库，请使用以下方式创建所有表:
        1. python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
        2. alembic stamp 001_initial

    如果已有数据库：
        alembic stamp 001_initial
    """
    # 检查表是否存在，如果不存在则创建
    # 这里我们使用 render_as_batch=True 模式，让 Alembic 处理 SQLite 的限制

    # 创建用户表
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('phone', sa.String(20), nullable=True, unique=True, index=True),
        sa.Column('email', sa.String(100), nullable=True, unique=True, index=True),
        sa.Column('password_hash', sa.String(128), nullable=True),
        sa.Column('nickname', sa.String(50), nullable=True),
        sa.Column('avatar', sa.String(255), nullable=True),
        sa.Column('gender', sa.String(10), nullable=True),
        sa.Column('birthday', sa.Date(), nullable=True),
        sa.Column('bio', sa.String(500), nullable=True),
        sa.Column('points', sa.Integer(), default=0),
        sa.Column('level', sa.Integer(), default=1),
        sa.Column('experience', sa.Integer(), default=0),
        sa.Column('vip_level', sa.Integer(), default=0),
        sa.Column('vip_expire_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Integer(), default=1),
        sa.Column('is_verified', sa.Integer(), default=0),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True
    )

    # 其他表由于数量众多，建议:
    # 1. 使用 Base.metadata.create_all() 创建
    # 2. 然后用 alembic stamp 001_initial 标记基线

    # 如需完整的初始迁移，请运行:
    # alembic revision --autogenerate -m "full initial migration"


def downgrade() -> None:
    """
    回滚数据库到上一版本

    警告: 此操作将删除所有数据!
    """
    # 按依赖顺序删除表
    tables_to_drop = [
        'audit_logs',
        'login_logs',
        'consultation_messages',
        'health_consultations',
        'health_records',
        'diagnosis_conversations',
        'health_diagnoses',
        'refund_requests',
        'product_reviews',
        'product_favorites',
        'order_items',
        'orders',
        'user_coupons',
        'coupons',
        'products',
        'product_categories',
        'notifications',
        'messages',
        'conversations',
        'activity_participants',
        'activities',
        'follows',
        'shares',
        'collection_folders',
        'collections',
        'topic_follows',
        'topics',
        'likes',
        'comments',
        'posts',
        'points_products',
        'points_records',
        'user_reports',
        'user_feedbacks',
        'user_addresses',
        'user_blacklists',
        'user_settings',
        'weight_records',
        'vaccination_records',
        'pet_photos',
        'pets',
        'pet_breeds',
        'users',
    ]

    for table in tables_to_drop:
        op.drop_table(table, if_exists=True)
