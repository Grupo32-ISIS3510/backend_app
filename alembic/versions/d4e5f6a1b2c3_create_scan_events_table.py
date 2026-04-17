"""create scan_events table for OCR telemetry

Revision ID: d4e5f6a1b2c3
Revises: b2c3d4e5f6a1
Create Date: 2026-03-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4e5f6a1b2c3'
down_revision: Union[str, None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scan_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('failure_reason', sa.String(255), nullable=True),
        sa.Column('products_detected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('received_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_index(
        'idx_scan_events_user_timestamp',
        'scan_events',
        ['user_id', 'timestamp'],
    )

    op.create_index(
        'idx_scan_events_success',
        'scan_events',
        ['success'],
    )


def downgrade() -> None:
    op.drop_index('idx_scan_events_success', table_name='scan_events')
    op.drop_index('idx_scan_events_user_timestamp', table_name='scan_events')
    op.drop_table('scan_events')
