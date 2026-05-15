"""add subscription payment orders

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payment_order',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('plan_id', sa.Text(), nullable=True),
        sa.Column('provider', sa.Text(), nullable=False, default='epay'),
        sa.Column('out_trade_no', sa.Text(), nullable=False),
        sa.Column('trade_no', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, default='pending'),
        sa.Column('amount_cents', sa.Integer(), nullable=False, default=0),
        sa.Column('currency', sa.Text(), nullable=False, default='CNY'),
        sa.Column('client_ip', sa.Text(), nullable=True),
        sa.Column('raw_notify', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.Column('paid_at', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plan.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('out_trade_no', name='uq_payment_order_out_trade_no'),
    )
    op.create_index('ix_payment_order_user_id', 'payment_order', ['user_id'])
    op.create_index('ix_payment_order_plan_id', 'payment_order', ['plan_id'])
    op.create_index('ix_payment_order_out_trade_no', 'payment_order', ['out_trade_no'])
    op.create_index('ix_payment_order_trade_no', 'payment_order', ['trade_no'])
    op.create_index('ix_payment_order_status', 'payment_order', ['status'])


def downgrade() -> None:
    op.drop_index('ix_payment_order_status', table_name='payment_order')
    op.drop_index('ix_payment_order_trade_no', table_name='payment_order')
    op.drop_index('ix_payment_order_out_trade_no', table_name='payment_order')
    op.drop_index('ix_payment_order_plan_id', table_name='payment_order')
    op.drop_index('ix_payment_order_user_id', table_name='payment_order')
    op.drop_table('payment_order')
