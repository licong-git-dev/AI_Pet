"""Add pet avatar tables (digital avatar, chat, stickers, personality)

Revision ID: 004_pet_avatar
Revises: 003_additional_indexes
Create Date: 2026-03-02

新增宠物数字分身相关的5个表：
- pet_avatars: 数字分身主表
- pet_avatar_chats: 对话会话表
- pet_avatar_messages: 对话消息表
- pet_stickers: 表情包表
- personality_profiles: 性格分析档案表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_pet_avatar'
down_revision: Union[str, None] = '003_additional_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建宠物数字分身相关表"""

    # ==================== pet_avatars ====================
    op.create_table(
        'pet_avatars',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('pet_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('appearance_desc', sa.Text(), nullable=True, comment='AI分析的外貌描述'),
        sa.Column('persona', sa.JSON(), nullable=True, comment='数字分身人设JSON'),
        sa.Column('speaking_style', sa.String(20), nullable=False, server_default='cute', comment='说话风格'),
        sa.Column('chat_count', sa.Integer(), server_default=sa.text('0'), comment='聊天次数'),
        sa.Column('sticker_count', sa.Integer(), server_default=sa.text('0'), comment='生成表情包次数'),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), comment='是否激活'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pet_avatars_pet_id', 'pet_avatars', ['pet_id'], unique=True)
    op.create_index('ix_pet_avatars_user_id', 'pet_avatars', ['user_id'])

    # ==================== pet_avatar_chats ====================
    op.create_table(
        'pet_avatar_chats',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('avatar_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(200), nullable=True, comment='会话标题'),
        sa.Column('message_count', sa.Integer(), server_default=sa.text('0'), comment='消息数量'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['avatar_id'], ['pet_avatars.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pet_avatar_chats_avatar_id', 'pet_avatar_chats', ['avatar_id'])
    op.create_index('ix_pet_avatar_chats_user_id', 'pet_avatar_chats', ['user_id'])

    # ==================== pet_avatar_messages ====================
    op.create_table(
        'pet_avatar_messages',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, comment='角色: user/assistant'),
        sa.Column('content', sa.Text(), nullable=False, comment='消息内容'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['chat_id'], ['pet_avatar_chats.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pet_avatar_messages_chat_id', 'pet_avatar_messages', ['chat_id'])

    # ==================== pet_stickers ====================
    op.create_table(
        'pet_stickers',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('pet_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('source_photo_url', sa.String(500), nullable=False, comment='原始照片URL'),
        sa.Column('emotion', sa.String(50), nullable=False, comment='表情类型'),
        sa.Column('prompt_used', sa.Text(), nullable=True, comment='生成所用的prompt'),
        sa.Column('sticker_url', sa.String(500), nullable=True, comment='表情包URL'),
        sa.Column('thumbnail_url', sa.String(500), nullable=True, comment='缩略图URL'),
        sa.Column('task_id', sa.String(100), nullable=True, comment='DashScope任务ID'),
        sa.Column('status', sa.String(20), server_default='pending', comment='状态: pending/generating/completed/failed'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('share_count', sa.Integer(), server_default=sa.text('0'), comment='分享次数'),
        sa.Column('save_count', sa.Integer(), server_default=sa.text('0'), comment='保存次数'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pet_stickers_pet_id', 'pet_stickers', ['pet_id'])
    op.create_index('ix_pet_stickers_user_id', 'pet_stickers', ['user_id'])
    op.create_index('ix_pet_stickers_status', 'pet_stickers', ['status'])

    # ==================== personality_profiles ====================
    op.create_table(
        'personality_profiles',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('pet_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('photo_url', sa.String(500), nullable=True, comment='分析使用的照片URL'),
        sa.Column('energy_level', sa.Integer(), nullable=True, comment='活泼度 0-100'),
        sa.Column('affection_level', sa.Integer(), nullable=True, comment='粘人度 0-100'),
        sa.Column('curiosity_level', sa.Integer(), nullable=True, comment='好奇心 0-100'),
        sa.Column('foodie_level', sa.Integer(), nullable=True, comment='吃货指数 0-100'),
        sa.Column('intelligence_level', sa.Integer(), nullable=True, comment='智商指数 0-100'),
        sa.Column('mischief_level', sa.Integer(), nullable=True, comment='调皮指数 0-100'),
        sa.Column('analysis_text', sa.Text(), nullable=True, comment='AI分析文本'),
        sa.Column('personality_tags', sa.JSON(), nullable=True, comment='性格标签JSON数组'),
        sa.Column('fun_description', sa.Text(), nullable=True, comment='趣味性格描述'),
        sa.Column('spirit_animal', sa.String(50), nullable=True, comment='灵魂动物'),
        sa.Column('motto', sa.String(200), nullable=True, comment='人生座右铭'),
        sa.Column('ai_model', sa.String(50), server_default='qwen-vl-max', comment='使用的AI模型'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['pet_id'], ['pets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_personality_profiles_pet_id', 'personality_profiles', ['pet_id'])
    op.create_index('ix_personality_profiles_user_id', 'personality_profiles', ['user_id'])


def downgrade() -> None:
    """删除宠物数字分身相关表"""
    op.drop_table('personality_profiles')
    op.drop_table('pet_stickers')
    op.drop_table('pet_avatar_messages')
    op.drop_table('pet_avatar_chats')
    op.drop_table('pet_avatars')
