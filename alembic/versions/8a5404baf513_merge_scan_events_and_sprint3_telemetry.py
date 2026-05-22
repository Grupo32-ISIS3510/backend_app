"""merge_scan_events_and_sprint3_telemetry

Revision ID: 8a5404baf513
Revises: d4e5f6a1b2c3, e5f6a7b8c9d0
Create Date: 2026-04-24 17:38:56.654274

"""
from typing import Sequence, Union

from alembic import op


revision: str = "8a5404baf513"
down_revision: Union[str, tuple[str, ...], None] = ("d4e5f6a1b2c3", "e5f6a7b8c9d0")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
