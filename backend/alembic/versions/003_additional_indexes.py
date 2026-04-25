"""Add additional indexes for query optimization

Revision ID: 003_additional_indexes
Revises: 002_indexes
Create Date: 2025-01-12

This migration adds additional indexes to optimize specific query patterns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_additional_indexes'
down_revision: Union[str, None] = '002_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add additional indexes for performance optimization"""

    # ===========================================
    # Points exchanges table indexes
    # ===========================================
    # Index for filtering user's exchanges by status
    op.create_index(
        'ix_points_exchanges_user_status',
        'points_exchanges',
        ['user_id', 'status', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # User coupons table indexes
    # ===========================================
    # Index for user's coupons by status
    op.create_index(
        'ix_user_coupons_user_status',
        'user_coupons',
        ['user_id', 'status', 'expire_at'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # User addresses table indexes
    # ===========================================
    # Index for user's default address
    op.create_index(
        'ix_user_addresses_user_default',
        'user_addresses',
        ['user_id', 'is_default'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Pets table indexes
    # ===========================================
    # Index for listing user's pets
    op.create_index(
        'ix_pets_owner_deleted',
        'pets',
        ['owner_id', 'deleted_at', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for pet type filtering
    op.create_index(
        'ix_pets_type',
        'pets',
        ['pet_type', 'deleted_at'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Consultations table indexes
    # ===========================================
    # Index for user's consultation history
    op.create_index(
        'ix_consultations_user_created',
        'health_consultations',
        ['user_id', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for pet's consultation history
    op.create_index(
        'ix_consultations_pet_created',
        'health_consultations',
        ['pet_id', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Product favorites table indexes
    # ===========================================
    # Unique constraint for user-product favorite
    op.create_index(
        'ix_product_favorites_user_product',
        'product_favorites',
        ['user_id', 'product_id'],
        unique=True,
        if_not_exists=True
    )

    # ===========================================
    # Refunds table indexes
    # ===========================================
    # Index for user's refund requests
    op.create_index(
        'ix_refunds_user_status',
        'refunds',
        ['user_id', 'status', 'created_at'],
        unique=False,
        if_not_exists=True
    )


def downgrade() -> None:
    """Remove all added indexes"""

    # Points exchanges indexes
    op.drop_index('ix_points_exchanges_user_status', table_name='points_exchanges', if_exists=True)

    # User coupons indexes
    op.drop_index('ix_user_coupons_user_status', table_name='user_coupons', if_exists=True)

    # User addresses indexes
    op.drop_index('ix_user_addresses_user_default', table_name='user_addresses', if_exists=True)

    # Pets indexes
    op.drop_index('ix_pets_owner_deleted', table_name='pets', if_exists=True)
    op.drop_index('ix_pets_type', table_name='pets', if_exists=True)

    # Consultations indexes
    op.drop_index('ix_consultations_user_created', table_name='health_consultations', if_exists=True)
    op.drop_index('ix_consultations_pet_created', table_name='health_consultations', if_exists=True)

    # Product favorites indexes
    op.drop_index('ix_product_favorites_user_product', table_name='product_favorites', if_exists=True)

    # Refunds indexes
    op.drop_index('ix_refunds_user_status', table_name='refunds', if_exists=True)
