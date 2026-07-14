"""add waiver period hours

Revision ID: 0033_add_waiver_period_hours
Revises: 0032_add_cfb27_player_fields
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0033_add_waiver_period_hours"
down_revision: str | None = "0032_add_cfb27_player_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "league_settings",
        sa.Column("waiver_period_hours", sa.Integer(), nullable=False, server_default="24"),
    )
    op.alter_column("league_settings", "waiver_period_hours", server_default=None)


def downgrade() -> None:
    op.drop_column("league_settings", "waiver_period_hours")
