"""add recipe_id to inventory_events (T3.2) and create recipe_favorites (T3.6)

Revision ID: h9i0j1k2l3m4
Revises: g8h9i0j1k2l3
Create Date: 2026-05-27 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'h9i0j1k2l3m4'
down_revision: Union[str, tuple[str, ...], None] = 'g8h9i0j1k2l3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T3.2 — link consumed inventory events back to the recipe that triggered the consumption.
    op.add_column(
        'inventory_events',
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_inventory_events_recipe_id',
        'inventory_events', 'recipes',
        ['recipe_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_inventory_events_recipe_id',
        'inventory_events',
        ['recipe_id'],
    )

    # T3.6 — recipe favorites per user.
    op.create_table(
        'recipe_favorites',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recipe_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('favorited_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'recipe_id', name='uq_recipe_favorites_user_recipe'),
    )
    op.create_index('ix_recipe_favorites_user_id', 'recipe_favorites', ['user_id'])
    op.create_index('ix_recipe_favorites_recipe_id', 'recipe_favorites', ['recipe_id'])


def downgrade() -> None:
    op.drop_index('ix_recipe_favorites_recipe_id', table_name='recipe_favorites')
    op.drop_index('ix_recipe_favorites_user_id', table_name='recipe_favorites')
    op.drop_table('recipe_favorites')

    op.drop_index('ix_inventory_events_recipe_id', table_name='inventory_events')
    op.drop_constraint('fk_inventory_events_recipe_id', 'inventory_events', type_='foreignkey')
    op.drop_column('inventory_events', 'recipe_id')
