"""add points recharge orders

Revision ID: 008_add_points_recharge_orders
Revises: 007_add_sku_id_to_order_items
Create Date: 2026-04-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_points_recharge_orders'
down_revision: Union[str, None] = '007_add_sku_id_to_order_items'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'points_recharge_orders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='充值订单ID'),
        sa.Column('order_no', sa.String(length=50), nullable=False, comment='充值订单号'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户ID'),
        sa.Column('package_code', sa.String(length=50), nullable=False, comment='套餐编码'),
        sa.Column('package_name', sa.String(length=100), nullable=False, comment='套餐名称'),
        sa.Column('points', sa.Integer(), nullable=False, comment='充值积分'),
        sa.Column('bonus_points', sa.Integer(), nullable=False, server_default='0', comment='赠送积分'),
        sa.Column('amount', sa.Float(), nullable=False, comment='支付金额'),
        sa.Column('pay_type', sa.String(length=20), nullable=True, comment='支付方式: wechat微信 alipay支付宝 balance余额'),
        sa.Column('pay_time', sa.DateTime(), nullable=True, comment='支付时间'),
        sa.Column('pay_trade_no', sa.String(length=100), nullable=True, comment='支付流水号'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', comment='状态: pending待支付 paid已支付 cancelled已取消'),
        sa.Column('credited_at', sa.DateTime(), nullable=True, comment='积分到账时间'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_no')
    )
    op.create_index(op.f('ix_points_recharge_orders_order_no'), 'points_recharge_orders', ['order_no'], unique=True)
    op.create_index(op.f('ix_points_recharge_orders_user_id'), 'points_recharge_orders', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_points_recharge_orders_user_id'), table_name='points_recharge_orders')
    op.drop_index(op.f('ix_points_recharge_orders_order_no'), table_name='points_recharge_orders')
    op.drop_table('points_recharge_orders')
