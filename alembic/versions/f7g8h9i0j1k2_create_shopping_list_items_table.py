"""create shopping_list_items table

Revision ID: f7g8h9i0j1k2
Revises: 8a5404baf513

Create Date: 2026-05-21 19:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f7g8h9i0j1k2'
down_revision: Union[str, None] = '8a5404baf513'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'shopping_list_items',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='Otros'),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=False, server_default='1'),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('purchased', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'),
        sa.Column('source_ref', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index(
        'ix_shopping_list_items_user_id',
        'shopping_list_items',
        ['user_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_shopping_list_items_user_id', table_name='shopping_list_items')
    op.drop_table('shopping_list_items')
