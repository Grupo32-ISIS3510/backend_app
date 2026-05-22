"""create feature_usage_events table (BQ T3.1)

Revision ID: g8h9i0j1k2l3
Revises: f7g8h9i0j1k2
Create Date: 2026-05-21 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'g8h9i0j1k2l3'
down_revision: Union[str, tuple[str, ...], None] = ('f7g8h9i0j1k2', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feature_usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('feature', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(
        'ix_feature_usage_events_user_id',
        'feature_usage_events',
        ['user_id'],
    )
    op.create_index(
        'ix_feature_usage_events_feature',
        'feature_usage_events',
        ['feature'],
    )
    # Indice compuesto: el GET stats filtra por timestamp y agrupa por feature.
    op.create_index(
        'ix_feature_usage_events_feature_timestamp',
        'feature_usage_events',
        ['feature', 'timestamp'],
    )


def downgrade() -> None:
    op.drop_index('ix_feature_usage_events_feature_timestamp', table_name='feature_usage_events')
    op.drop_index('ix_feature_usage_events_feature', table_name='feature_usage_events')
    op.drop_index('ix_feature_usage_events_user_id', table_name='feature_usage_events')
    op.drop_table('feature_usage_events')
