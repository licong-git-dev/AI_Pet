"""add sku_id to order_items

Revision ID: 007_add_sku_id_to_order_items
Revises: 006_fix_personality_profile
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_sku_id_to_order_items'
down_revision: Union[str, None] = '006_fix_personality_profile'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('order_items') as batch_op:
        batch_op.add_column(sa.Column('sku_id', sa.BigInteger(), nullable=True, comment='SKU ID'))


def downgrade() -> None:
    with op.batch_alter_table('order_items') as batch_op:
        batch_op.drop_column('sku_id')
