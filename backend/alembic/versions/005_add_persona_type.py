"""Add PetSona persona type fields to personality_profiles

Revision ID: 005_persona_type
Revises: 004_pet_avatar
Create Date: 2026-03-03

新增5个字段支持PetSona"宠物版MBTI"类型系统：
- persona_type: 类型ID (如 solar_explorer)
- persona_type_name: 类型中文名 (如 阳光探险家)
- persona_type_emoji: 类型emoji (如 ☀️🧭)
- persona_type_color: 类型主题色 (如 #FF9800)
- persona_type_slogan: 类型标语 (如 每一天都是新冒险！)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_persona_type'
down_revision: Union[str, None] = '004_pet_avatar'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 PetSona 类型字段"""
    op.add_column('personality_profiles', sa.Column('persona_type', sa.String(30), nullable=True, comment='PetSona类型ID'))
    op.add_column('personality_profiles', sa.Column('persona_type_name', sa.String(20), nullable=True, comment='PetSona类型名'))
    op.add_column('personality_profiles', sa.Column('persona_type_emoji', sa.String(10), nullable=True, comment='PetSona类型emoji'))
    op.add_column('personality_profiles', sa.Column('persona_type_color', sa.String(10), nullable=True, comment='PetSona类型颜色'))
    op.add_column('personality_profiles', sa.Column('persona_type_slogan', sa.String(50), nullable=True, comment='PetSona类型标语'))


def downgrade() -> None:
    """移除 PetSona 类型字段"""
    op.drop_column('personality_profiles', 'persona_type_slogan')
    op.drop_column('personality_profiles', 'persona_type_color')
    op.drop_column('personality_profiles', 'persona_type_emoji')
    op.drop_column('personality_profiles', 'persona_type_name')
    op.drop_column('personality_profiles', 'persona_type')
