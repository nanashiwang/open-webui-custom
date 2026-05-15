"""add subscription tables

Revision ID: e5f6a7b8c9d0
Revises: 4de81c2a3af1, d4e5f6a7b8c9, c0fbf31ca0db
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = ('4de81c2a3af1', 'd4e5f6a7b8c9', 'c0fbf31ca0db')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'subscription_plan',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_cents', sa.Integer(), nullable=False, default=0),
        sa.Column('currency', sa.Text(), nullable=False, default='USD'),
        sa.Column('interval', sa.Text(), nullable=False, default='month'),
        sa.Column('token_limit', sa.BigInteger(), nullable=True),
        sa.Column('request_limit', sa.BigInteger(), nullable=True),
        sa.Column('model_ids', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
    )

    op.create_table(
        'user_subscription',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('plan_id', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, default='active'),
        sa.Column('current_period_start', sa.BigInteger(), nullable=False),
        sa.Column('current_period_end', sa.BigInteger(), nullable=False),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plan.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_user_subscription_user_id', 'user_subscription', ['user_id'])
    op.create_index('ix_user_subscription_plan_id', 'user_subscription', ['plan_id'])

    op.create_table(
        'usage_ledger',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('subscription_id', sa.Text(), nullable=True),
        sa.Column('plan_id', sa.Text(), nullable=True),
        sa.Column('model_id', sa.Text(), nullable=True),
        sa.Column('chat_id', sa.Text(), nullable=True),
        sa.Column('message_id', sa.Text(), nullable=True),
        sa.Column('event_type', sa.Text(), nullable=False, default='chat_completion'),
        sa.Column('input_tokens', sa.BigInteger(), nullable=False, default=0),
        sa.Column('output_tokens', sa.BigInteger(), nullable=False, default=0),
        sa.Column('total_tokens', sa.BigInteger(), nullable=False, default=0),
        sa.Column('request_count', sa.BigInteger(), nullable=False, default=1),
        sa.Column('estimated', sa.Boolean(), nullable=False, default=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('chat_id', 'message_id', 'event_type', name='uq_usage_ledger_message_event'),
    )
    op.create_index('ix_usage_ledger_user_id', 'usage_ledger', ['user_id'])
    op.create_index('ix_usage_ledger_subscription_id', 'usage_ledger', ['subscription_id'])
    op.create_index('ix_usage_ledger_plan_id', 'usage_ledger', ['plan_id'])
    op.create_index('ix_usage_ledger_model_id', 'usage_ledger', ['model_id'])
    op.create_index('ix_usage_ledger_chat_id', 'usage_ledger', ['chat_id'])
    op.create_index('ix_usage_ledger_user_created', 'usage_ledger', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_usage_ledger_user_created', table_name='usage_ledger')
    op.drop_index('ix_usage_ledger_chat_id', table_name='usage_ledger')
    op.drop_index('ix_usage_ledger_model_id', table_name='usage_ledger')
    op.drop_index('ix_usage_ledger_plan_id', table_name='usage_ledger')
    op.drop_index('ix_usage_ledger_subscription_id', table_name='usage_ledger')
    op.drop_index('ix_usage_ledger_user_id', table_name='usage_ledger')
    op.drop_table('usage_ledger')
    op.drop_index('ix_user_subscription_plan_id', table_name='user_subscription')
    op.drop_index('ix_user_subscription_user_id', table_name='user_subscription')
    op.drop_table('user_subscription')
    op.drop_table('subscription_plan')
