"""store kickoff-aware lineup snapshot locks

Revision ID: 0034_lineup_snapshot_kickoff_lock
Revises: 0033_add_waiver_period_hours
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0034_lineup_kickoff_lock"
down_revision: str | None = "0033_add_waiver_period_hours"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lineup_week_snapshots", sa.Column("game_start_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column(
        "lineup_week_snapshots",
        "locked_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "lineup_week_snapshots",
        "locked_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_column("lineup_week_snapshots", "game_start_at")
