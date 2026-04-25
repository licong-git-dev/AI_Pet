"""Add indexes for query optimization

Revision ID: 002_indexes
Revises: 001_initial
Create Date: 2025-01-05

This migration adds indexes to optimize common query patterns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_indexes'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add indexes for performance optimization"""

    # ===========================================
    # Posts table indexes
    # ===========================================
    # Index for listing published posts ordered by time
    op.create_index(
        'ix_posts_status_deleted_created',
        'posts',
        ['status', 'deleted_at', 'created_at'],
        unique=False,
        postgresql_ops={'created_at': 'DESC'},
        if_not_exists=True
    )

    # Index for hot posts
    op.create_index(
        'ix_posts_is_hot',
        'posts',
        ['is_hot', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for content type filtering
    op.create_index(
        'ix_posts_content_type',
        'posts',
        ['content_type'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Likes table indexes
    # ===========================================
    # Unique constraint for user-target combination
    op.create_index(
        'ix_likes_user_target',
        'likes',
        ['user_id', 'target_type', 'target_id'],
        unique=True,
        if_not_exists=True
    )

    # Index for counting likes on a target
    op.create_index(
        'ix_likes_target',
        'likes',
        ['target_type', 'target_id'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Comments table indexes
    # ===========================================
    # Index for listing comments ordered by time
    op.create_index(
        'ix_comments_post_created',
        'comments',
        ['post_id', 'status', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Follows table indexes
    # ===========================================
    # Unique constraint for follow relationship
    op.create_index(
        'ix_follows_follower_following',
        'follows',
        ['follower_id', 'following_id'],
        unique=True,
        if_not_exists=True
    )

    # ===========================================
    # Notifications table indexes
    # ===========================================
    # Index for user's unread notifications
    op.create_index(
        'ix_notifications_user_read_created',
        'notifications',
        ['user_id', 'is_read', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Orders table indexes
    # ===========================================
    # Index for user's orders by status
    op.create_index(
        'ix_orders_user_status',
        'orders',
        ['user_id', 'status', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for order number lookup
    op.create_index(
        'ix_orders_order_no',
        'orders',
        ['order_no'],
        unique=True,
        if_not_exists=True
    )

    # ===========================================
    # Points records table indexes
    # ===========================================
    # Index for user's points history
    op.create_index(
        'ix_points_records_user_created',
        'points_records',
        ['user_id', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for source type filtering
    op.create_index(
        'ix_points_records_source_type',
        'points_records',
        ['user_id', 'source_type'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Activities table indexes
    # ===========================================
    # Index for upcoming activities
    op.create_index(
        'ix_activities_status_start',
        'activities',
        ['status', 'start_time'],
        unique=False,
        if_not_exists=True
    )

    # Index for activity type filtering
    op.create_index(
        'ix_activities_type',
        'activities',
        ['activity_type', 'status'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Messages table indexes
    # ===========================================
    # Index for conversation messages
    op.create_index(
        'ix_messages_conversation_created',
        'messages',
        ['conversation_id', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for unread messages
    op.create_index(
        'ix_messages_receiver_read',
        'messages',
        ['receiver_id', 'is_read'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Products table indexes
    # ===========================================
    # Index for product listing
    op.create_index(
        'ix_products_status_category',
        'products',
        ['status', 'category_id', 'deleted_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for hot products
    op.create_index(
        'ix_products_is_hot',
        'products',
        ['is_hot', 'sort_order'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Health records table indexes
    # ===========================================
    # Index for user's health records
    op.create_index(
        'ix_health_records_user_created',
        'health_records',
        ['user_id', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # Index for pet's health records
    op.create_index(
        'ix_health_records_pet_created',
        'health_records',
        ['pet_id', 'created_at'],
        unique=False,
        if_not_exists=True
    )

    # ===========================================
    # Diagnosis records table indexes
    # ===========================================
    # Index for user's diagnosis history
    op.create_index(
        'ix_diagnosis_records_user_created',
        'diagnosis_records',
        ['user_id', 'created_at'],
        unique=False,
        if_not_exists=True
    )


def downgrade() -> None:
    """Remove all added indexes"""

    # Posts indexes
    op.drop_index('ix_posts_status_deleted_created', table_name='posts', if_exists=True)
    op.drop_index('ix_posts_is_hot', table_name='posts', if_exists=True)
    op.drop_index('ix_posts_content_type', table_name='posts', if_exists=True)

    # Likes indexes
    op.drop_index('ix_likes_user_target', table_name='likes', if_exists=True)
    op.drop_index('ix_likes_target', table_name='likes', if_exists=True)

    # Comments indexes
    op.drop_index('ix_comments_post_created', table_name='comments', if_exists=True)

    # Follows indexes
    op.drop_index('ix_follows_follower_following', table_name='follows', if_exists=True)

    # Notifications indexes
    op.drop_index('ix_notifications_user_read_created', table_name='notifications', if_exists=True)

    # Orders indexes
    op.drop_index('ix_orders_user_status', table_name='orders', if_exists=True)
    op.drop_index('ix_orders_order_no', table_name='orders', if_exists=True)

    # Points records indexes
    op.drop_index('ix_points_records_user_created', table_name='points_records', if_exists=True)
    op.drop_index('ix_points_records_source_type', table_name='points_records', if_exists=True)

    # Activities indexes
    op.drop_index('ix_activities_status_start', table_name='activities', if_exists=True)
    op.drop_index('ix_activities_type', table_name='activities', if_exists=True)

    # Messages indexes
    op.drop_index('ix_messages_conversation_created', table_name='messages', if_exists=True)
    op.drop_index('ix_messages_receiver_read', table_name='messages', if_exists=True)

    # Products indexes
    op.drop_index('ix_products_status_category', table_name='products', if_exists=True)
    op.drop_index('ix_products_is_hot', table_name='products', if_exists=True)

    # Health records indexes
    op.drop_index('ix_health_records_user_created', table_name='health_records', if_exists=True)
    op.drop_index('ix_health_records_pet_created', table_name='health_records', if_exists=True)

    # Diagnosis records indexes
    op.drop_index('ix_diagnosis_records_user_created', table_name='diagnosis_records', if_exists=True)
