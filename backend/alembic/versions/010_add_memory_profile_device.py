"""add memory, owner_profile, device_bindings tables

Revision ID: 010_add_memory_profile_device
Revises: 009_add_membership_orders
Create Date: 2026-04-25

引入三大支柱所需的数据表：
- pet_memories / memory_digests
- owner_profiles / owner_signals
- device_bindings
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_add_memory_profile_device'
down_revision: Union[str, None] = '009_add_membership_orders'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== pet_memories ====================
    op.create_table(
        'pet_memories',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='记忆ID'),
        sa.Column('pet_avatar_id', sa.BigInteger(), nullable=False, comment='所属分身ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='所属用户ID'),
        sa.Column('memory_type', sa.String(length=20), nullable=False, comment='episodic/semantic/preference/event'),
        sa.Column('content', sa.Text(), nullable=False, comment='记忆原文'),
        sa.Column('summary', sa.String(length=255), nullable=True, comment='一句话摘要'),
        sa.Column('importance', sa.SmallInteger(), nullable=False, server_default=sa.text('5'), comment='重要度 0-10'),
        sa.Column('emotion', sa.String(length=20), nullable=True),
        sa.Column('emotion_intensity', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='conversation'),
        sa.Column('source_ref', sa.String(length=100), nullable=True),
        sa.Column('happened_at', sa.DateTime(), nullable=True),
        sa.Column('embedding_vector_id', sa.String(length=64), nullable=True),
        sa.Column('last_recalled_at', sa.DateTime(), nullable=True),
        sa.Column('recall_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('effective_strength', sa.Float(), server_default=sa.text('1.0')),
        sa.Column('is_archived', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('is_pinned', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['pet_avatar_id'], ['pet_avatars.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pet_memories_pet_avatar_id', 'pet_memories', ['pet_avatar_id'])
    op.create_index('ix_pet_memories_user_id', 'pet_memories', ['user_id'])
    op.create_index('ix_pet_memories_memory_type', 'pet_memories', ['memory_type'])
    op.create_index('ix_pet_memories_avatar_type', 'pet_memories', ['pet_avatar_id', 'memory_type'])
    op.create_index('ix_pet_memories_user_archived', 'pet_memories', ['user_id', 'is_archived'])
    op.create_index('ix_pet_memories_strength', 'pet_memories', ['effective_strength'])

    # ==================== memory_digests ====================
    op.create_table(
        'memory_digests',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('pet_avatar_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('period_type', sa.String(length=10), nullable=False, comment='daily/weekly/monthly'),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('key_themes', sa.JSON(), nullable=True),
        sa.Column('dominant_emotion', sa.String(length=20), nullable=True),
        sa.Column('sourced_memory_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['pet_avatar_id'], ['pet_avatars.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_memory_digests_pet_avatar_id', 'memory_digests', ['pet_avatar_id'])
    op.create_index('ix_memory_digests_user_id', 'memory_digests', ['user_id'])
    op.create_index('ix_memory_digests_avatar_period', 'memory_digests', ['pet_avatar_id', 'period_type', 'period_start'])

    # ==================== owner_profiles ====================
    op.create_table(
        'owner_profiles',
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户ID'),
        sa.Column('daily_rhythm', sa.JSON(), nullable=True),
        sa.Column('emotional_baseline', sa.JSON(), nullable=True),
        sa.Column('relationships', sa.JSON(), nullable=True),
        sa.Column('communication', sa.JSON(), nullable=True),
        sa.Column('pet_attachment', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), server_default=sa.text('0.0')),
        sa.Column('signal_count', sa.Integer(), server_default=sa.text('0')),
        sa.Column('last_built_at', sa.DateTime(), nullable=True),
        sa.Column('is_visible_to_avatar', sa.Boolean(), server_default=sa.text('1')),
        sa.Column('is_learning_paused', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('pause_until', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id'),
    )

    # ==================== owner_signals ====================
    op.create_table(
        'owner_signals',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('signal_type', sa.String(length=20), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_label', sa.String(length=20), nullable=True),
        sa.Column('text_excerpt', sa.String(length=255), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_owner_signals_user_id', 'owner_signals', ['user_id'])
    op.create_index('ix_owner_signals_signal_type', 'owner_signals', ['signal_type'])
    op.create_index('ix_owner_signals_recorded_at', 'owner_signals', ['recorded_at'])
    op.create_index('ix_owner_signals_user_type_time', 'owner_signals', ['user_id', 'signal_type', 'recorded_at'])

    # ==================== device_bindings ====================
    op.create_table(
        'device_bindings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('pet_avatar_id', sa.BigInteger(), nullable=True),
        sa.Column('device_type', sa.String(length=20), nullable=False),
        sa.Column('device_id', sa.String(length=64), nullable=False),
        sa.Column('device_name', sa.String(length=50), nullable=True),
        sa.Column('capabilities', sa.JSON(), nullable=True),
        sa.Column('pairing_code', sa.String(length=16), nullable=True),
        sa.Column('pairing_expires_at', sa.DateTime(), nullable=True),
        sa.Column('transport', sa.String(length=20), nullable=False, server_default='websocket'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_event_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pet_avatar_id'], ['pet_avatars.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_type', 'device_id', name='uq_device_type_id'),
    )
    op.create_index('ix_device_bindings_user_id', 'device_bindings', ['user_id'])
    op.create_index('ix_device_bindings_pet_avatar_id', 'device_bindings', ['pet_avatar_id'])
    op.create_index('ix_device_bindings_device_type', 'device_bindings', ['device_type'])
    op.create_index('ix_device_bindings_pairing_code', 'device_bindings', ['pairing_code'])
    op.create_index('ix_device_bindings_status', 'device_bindings', ['status'])
    op.create_index('ix_device_bindings_user_status', 'device_bindings', ['user_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_device_bindings_user_status', table_name='device_bindings')
    op.drop_index('ix_device_bindings_status', table_name='device_bindings')
    op.drop_index('ix_device_bindings_pairing_code', table_name='device_bindings')
    op.drop_index('ix_device_bindings_device_type', table_name='device_bindings')
    op.drop_index('ix_device_bindings_pet_avatar_id', table_name='device_bindings')
    op.drop_index('ix_device_bindings_user_id', table_name='device_bindings')
    op.drop_table('device_bindings')

    op.drop_index('ix_owner_signals_user_type_time', table_name='owner_signals')
    op.drop_index('ix_owner_signals_recorded_at', table_name='owner_signals')
    op.drop_index('ix_owner_signals_signal_type', table_name='owner_signals')
    op.drop_index('ix_owner_signals_user_id', table_name='owner_signals')
    op.drop_table('owner_signals')

    op.drop_table('owner_profiles')

    op.drop_index('ix_memory_digests_avatar_period', table_name='memory_digests')
    op.drop_index('ix_memory_digests_user_id', table_name='memory_digests')
    op.drop_index('ix_memory_digests_pet_avatar_id', table_name='memory_digests')
    op.drop_table('memory_digests')

    op.drop_index('ix_pet_memories_strength', table_name='pet_memories')
    op.drop_index('ix_pet_memories_user_archived', table_name='pet_memories')
    op.drop_index('ix_pet_memories_avatar_type', table_name='pet_memories')
    op.drop_index('ix_pet_memories_memory_type', table_name='pet_memories')
    op.drop_index('ix_pet_memories_user_id', table_name='pet_memories')
    op.drop_index('ix_pet_memories_pet_avatar_id', table_name='pet_memories')
    op.drop_table('pet_memories')
