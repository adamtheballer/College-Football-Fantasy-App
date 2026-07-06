"""Add live scoring engine tables.

Revision ID: 0022_live_scoring_engine
Revises: 0021_auth_hardening
Create Date: 2026-07-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0022_live_scoring_engine"
down_revision: str | None = "0021_auth_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_week_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("fantasy_points", sa.Float(), server_default="0", nullable=False),
        sa.Column("breakdown_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("source_stat_id", sa.Integer(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_stat_id"], ["player_stats.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("league_id", "player_id", "season", "week", name="uq_player_week_scores_league_player_week"),
    )
    op.create_index("ix_player_week_scores_league_week", "player_week_scores", ["league_id", "season", "week"])
    op.create_index("ix_player_week_scores_player_id", "player_week_scores", ["player_id"])

    op.add_column("team_week_scores", sa.Column("starter_points", sa.Float(), server_default="0", nullable=False))
    op.add_column("team_week_scores", sa.Column("bench_points", sa.Float(), server_default="0", nullable=False))
    op.add_column("team_week_scores", sa.Column("total_points", sa.Float(), server_default="0", nullable=False))
    op.add_column("team_week_scores", sa.Column("breakdown_json", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False))
    op.add_column("team_week_scores", sa.Column("status", sa.String(length=50), server_default="live", nullable=False))
    op.add_column("team_week_scores", sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint(
        "uq_team_week_scores_league_team_week",
        "team_week_scores",
        ["league_id", "team_id", "season", "week"],
    )

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

    op.create_table(
        "scoring_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), server_default="sportsdata", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="running", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("players_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("teams_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matchups_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_runs_league_week", "scoring_runs", ["league_id", "season", "week"])
    op.create_index("ix_scoring_runs_status", "scoring_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_scoring_runs_status", table_name="scoring_runs")
    op.drop_index("ix_scoring_runs_league_week", table_name="scoring_runs")
    op.drop_table("scoring_runs")

    op.drop_index("ix_lineup_snapshots_team_week", table_name="lineup_week_snapshots")
    op.drop_index("ix_lineup_snapshots_league_week", table_name="lineup_week_snapshots")
    op.drop_table("lineup_week_snapshots")

    op.drop_constraint("uq_team_week_scores_league_team_week", "team_week_scores", type_="unique")
    op.drop_column("team_week_scores", "calculated_at")
    op.drop_column("team_week_scores", "status")
    op.drop_column("team_week_scores", "breakdown_json")
    op.drop_column("team_week_scores", "total_points")
    op.drop_column("team_week_scores", "bench_points")
    op.drop_column("team_week_scores", "starter_points")

    op.drop_index("ix_player_week_scores_player_id", table_name="player_week_scores")
    op.drop_index("ix_player_week_scores_league_week", table_name="player_week_scores")
    op.drop_table("player_week_scores")
