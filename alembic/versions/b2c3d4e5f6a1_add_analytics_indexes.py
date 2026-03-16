"""add analytics indexes on inventory_events

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-03-16 12:01:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Índice compuesto para los queries de analytics sobre inventory_events.
    # Evita full table scan al filtrar por usuario, tipo de evento y rango de fechas.
    op.create_index(
        'idx_inventory_events_user_type_time',
        'inventory_events',
        ['user_id', 'event_type', 'occurred_at'],
    )

    # Índice adicional para JOIN con inventory_items en el cálculo de savings/waste
    op.create_index(
        'idx_inventory_events_item_id',
        'inventory_events',
        ['item_id'],
    )

    # Índice para recipe_interactions — usado en get_user_segment (últimos 30 días)
    op.create_index(
        'idx_recipe_interactions_user_action_time',
        'recipe_interactions',
        ['user_id', 'action', 'occurred_at'],
    )


def downgrade() -> None:
    op.drop_index('idx_recipe_interactions_user_action_time', table_name='recipe_interactions')
    op.drop_index('idx_inventory_events_item_id', table_name='inventory_events')
    op.drop_index('idx_inventory_events_user_type_time', table_name='inventory_events')
