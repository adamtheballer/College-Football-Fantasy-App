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


def _create_missing_snapshot_table() -> None:
    op.create_table(
        "lineup_week_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(length=50), nullable=False),
        sa.Column("is_starter", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "team_id", "player_id", "season", "week", name="uq_lineup_snapshot_player_week"),
    )
    op.create_index("ix_lineup_snapshots_league_week", "lineup_week_snapshots", ["league_id", "season", "week"])
    op.create_index("ix_lineup_snapshots_team_week", "lineup_week_snapshots", ["team_id", "season", "week"])


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("lineup_week_snapshots"):
        _create_missing_snapshot_table()
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
