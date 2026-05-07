"""add inventory_matches to recipe_interactions

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6, d4e5f6a1b2c3
Create Date: 2026-05-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str]] = ('e1f2a3b4c5d6', 'd4e5f6a1b2c3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'recipe_interactions',
        sa.Column('inventory_matches', sa.Integer(), nullable=True),
    )
    op.create_index(
        'ix_recipe_interactions_action_occurred',
        'recipe_interactions',
        ['action', 'occurred_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_recipe_interactions_action_occurred', table_name='recipe_interactions')
    op.drop_column('recipe_interactions', 'inventory_matches')
