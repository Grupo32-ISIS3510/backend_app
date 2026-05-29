"""create analytics_events table

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-03-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a1b2'
down_revision: Union[str, None] = 'b2c3d4e5f6a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'analytics_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('event_name', sa.String(length=100), nullable=False),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('platform', sa.String(length=20), nullable=True),
        sa.Column('app_version', sa.String(length=20), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'idx_analytics_events_user_name_time',
        'analytics_events',
        ['user_id', 'event_name', 'occurred_at'],
    )

    op.create_index(
        'idx_analytics_events_session',
        'analytics_events',
        ['session_id'],
    )


def downgrade() -> None:
    op.drop_index('idx_analytics_events_session', table_name='analytics_events')
    op.drop_index('idx_analytics_events_user_name_time', table_name='analytics_events')
    op.drop_table('analytics_events')
