"""scoring pipeline tables

Revision ID: 0003_scoring_pipeline
Revises: 0002_player_stats
Create Date: 2024-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_scoring_pipeline"
down_revision = "0002_player_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_week_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("points_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("points_starters", sa.Float(), nullable=False, server_default="0"),
        sa.Column("points_bench", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("team_id", "season", "week", name="uq_team_week_scores_team_season_week"),
    )
    op.create_index("ix_team_week_scores_team_id", "team_week_scores", ["team_id"])
    op.create_index("ix_team_week_scores_league_week", "team_week_scores", ["league_id", "season", "week"])

    op.create_table(
        "matchups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("home_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("away_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="scheduled"),
        sa.Column("home_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("away_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "league_id", "season", "week", "home_team_id", "away_team_id", name="uq_matchup_unique"
        ),
    )
    op.create_index("ix_matchups_league_week", "matchups", ["league_id", "season", "week"])

    op.create_table(
        "standings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("wins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ties", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_for", sa.Float(), nullable=False, server_default="0"),
        sa.Column("points_against", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("league_id", "team_id", "season", "week", name="uq_standings_team_season_week"),
    )
    op.create_index("ix_standings_league_week", "standings", ["league_id", "season", "week"])


def downgrade() -> None:
    op.drop_index("ix_standings_league_week", table_name="standings")
    op.drop_table("standings")

    op.drop_index("ix_matchups_league_week", table_name="matchups")
    op.drop_table("matchups")

    op.drop_index("ix_team_week_scores_league_week", table_name="team_week_scores")
    op.drop_index("ix_team_week_scores_team_id", table_name="team_week_scores")
    op.drop_table("team_week_scores")
