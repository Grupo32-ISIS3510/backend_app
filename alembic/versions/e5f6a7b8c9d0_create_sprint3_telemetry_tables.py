"""create expiry_accuracy_events and screen_events tables for Sprint 3

Revision ID: e5f6a7b8c9d0
Revises: e1f2a3b4c5d6
Create Date: 2026-03-18 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T3.3 — Expiry Accuracy Events
    op.create_table(
        'expiry_accuracy_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('category', sa.String(100), nullable=False, index=True),
        sa.Column('ocr_detected_date', sa.Boolean(), nullable=False),
        sa.Column('ocr_date', sa.Date(), nullable=True),
        sa.Column('user_confirmed_date', sa.Date(), nullable=False),
        sa.Column('accurate', sa.Boolean(), nullable=False),
        sa.Column('received_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index(
        'idx_expiry_accuracy_category_accurate',
        'expiry_accuracy_events',
        ['category', 'accurate'],
    )

    # T3.5 — Screen Events
    op.create_table(
        'screen_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('screen_name', sa.String(100), nullable=False, index=True),
        sa.Column('event_type', sa.String(20), nullable=False),
        sa.Column('exit_reason', sa.String(100), nullable=True),
        sa.Column('dwell_time_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('received_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index(
        'idx_screen_events_screen_type',
        'screen_events',
        ['screen_name', 'event_type'],
    )


def downgrade() -> None:
    op.drop_index('idx_screen_events_screen_type', table_name='screen_events')
    op.drop_table('screen_events')
    op.drop_index('idx_expiry_accuracy_category_accurate', table_name='expiry_accuracy_events')
    op.drop_table('expiry_accuracy_events')
