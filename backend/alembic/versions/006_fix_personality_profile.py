"""Fix PersonalityProfile column sizes and add updated_at

Revision ID: 006_fix_personality_profile
Revises: 005_persona_type
Create Date: 2026-03-10

修复内容：
1. persona_type_name: String(20) → String(50)（预留空间）
2. persona_type_emoji: String(10) → String(20)（支持多码点emoji变体序列）
3. persona_type_slogan: String(50) → String(100)（与 motto String(200) 保持合理比例）
4. 补充 updated_at 列（项目规范要求所有表都有 created_at 和 updated_at）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '006_fix_personality_profile'
down_revision: Union[str, None] = '005_persona_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 扩大列宽
    op.alter_column('personality_profiles', 'persona_type_name',
                    existing_type=sa.String(20), type_=sa.String(50), existing_nullable=True)
    op.alter_column('personality_profiles', 'persona_type_emoji',
                    existing_type=sa.String(10), type_=sa.String(20), existing_nullable=True)
    op.alter_column('personality_profiles', 'persona_type_slogan',
                    existing_type=sa.String(50), type_=sa.String(100), existing_nullable=True)
    # 补充 updated_at（符合项目 DB 规范）
    # server_default 只设置 INSERT 时的默认值；UPDATE 时的自动更新由 ORM onupdate= 处理，
    # 不应将 ON UPDATE 写入 server_default（会导致 Alembic autogenerate drift）
    op.add_column('personality_profiles',
                  sa.Column('updated_at', sa.DateTime(),
                            server_default=sa.text('CURRENT_TIMESTAMP'),
                            nullable=True, comment='更新时间'))


def downgrade() -> None:
    op.drop_column('personality_profiles', 'updated_at')
    op.alter_column('personality_profiles', 'persona_type_slogan',
                    existing_type=sa.String(100), type_=sa.String(50), existing_nullable=True)
    op.alter_column('personality_profiles', 'persona_type_emoji',
                    existing_type=sa.String(20), type_=sa.String(10), existing_nullable=True)
    op.alter_column('personality_profiles', 'persona_type_name',
                    existing_type=sa.String(50), type_=sa.String(20), existing_nullable=True)
