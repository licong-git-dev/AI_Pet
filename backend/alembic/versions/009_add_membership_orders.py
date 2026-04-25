"""add membership orders

Revision ID: 009_add_membership_orders
Revises: 008_add_points_recharge_orders
Create Date: 2026-04-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_membership_orders'
down_revision: Union[str, None] = '008_add_points_recharge_orders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'membership_orders',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='会员订单ID'),
        sa.Column('order_no', sa.String(length=50), nullable=False, comment='会员订单号'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户ID'),
        sa.Column('plan_code', sa.String(length=50), nullable=False, comment='会员套餐编码'),
        sa.Column('plan_name', sa.String(length=100), nullable=False, comment='会员套餐名称'),
        sa.Column('member_level', sa.Integer(), nullable=False, comment='会员等级'),
        sa.Column('duration_days', sa.Integer(), nullable=False, comment='会员时长(天)'),
        sa.Column('amount', sa.Float(), nullable=False, comment='支付金额'),
        sa.Column('pay_type', sa.String(length=20), nullable=True, comment='支付方式: wechat微信 alipay支付宝 balance余额'),
        sa.Column('pay_time', sa.DateTime(), nullable=True, comment='支付时间'),
        sa.Column('pay_trade_no', sa.String(length=100), nullable=True, comment='支付流水号'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', comment='状态: pending待支付 paid已支付 cancelled已取消'),
        sa.Column('fulfilled_at', sa.DateTime(), nullable=True, comment='会员生效时间'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_no')
    )
    op.create_index(op.f('ix_membership_orders_order_no'), 'membership_orders', ['order_no'], unique=True)
    op.create_index(op.f('ix_membership_orders_user_id'), 'membership_orders', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_membership_orders_user_id'), table_name='membership_orders')
    op.drop_index(op.f('ix_membership_orders_order_no'), table_name='membership_orders')
    op.drop_table('membership_orders')
