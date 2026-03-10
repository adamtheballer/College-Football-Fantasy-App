"""team stats snapshots

Revision ID: 0008_team_stats
Revises: 0007_notif_league_prefs
Create Date: 2026-03-09 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_team_stats"
down_revision = "0007_notif_league_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_stats_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("conference", sa.String(length=10), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scope", sa.String(length=30), nullable=False, server_default="season"),
        sa.Column("offense_stats", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("defense_stats", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("advanced_stats", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="cfbd"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "team_name",
            "season",
            "week",
            "scope",
            name="uq_team_stats_snapshot_team_season_week_scope",
        ),
    )
    op.create_index("ix_team_stats_snapshots_team_name", "team_stats_snapshots", ["team_name"])
    op.create_index("ix_team_stats_snapshots_conference", "team_stats_snapshots", ["conference"])
    op.create_index("ix_team_stats_snapshots_season_week", "team_stats_snapshots", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_team_stats_snapshots_season_week", table_name="team_stats_snapshots")
    op.drop_index("ix_team_stats_snapshots_conference", table_name="team_stats_snapshots")
    op.drop_index("ix_team_stats_snapshots_team_name", table_name="team_stats_snapshots")
    op.drop_table("team_stats_snapshots")
