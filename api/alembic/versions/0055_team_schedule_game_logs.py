"""Add canonical team-week schedules for player game logs.

Revision ID: 0055_team_schedule_game_logs
Revises: 0054_add_reveal_all_waiver_bids
"""

from alembic import op
import sqlalchemy as sa


revision = "0055_team_schedule_game_logs"
down_revision = "0054_add_reveal_all_waiver_bids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opponent_name", sa.String(length=200), nullable=True),
        sa.Column("location", sa.String(length=16), nullable=False),
        sa.Column("is_bye", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("game_date", sa.Date(), nullable=True),
        sa.Column("kickoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("neutral_site", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("conference_game", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("venue", sa.String(length=300), nullable=True),
        sa.Column("tv_network", sa.String(length=120), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("primary_source_url", sa.String(length=500), nullable=True),
        sa.Column("date_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("team_name", "season", "week", name="uq_team_schedules_team_season_week"),
        sa.CheckConstraint("location IN ('home', 'away', 'neutral', 'bye')", name="ck_team_schedules_location"),
    )
    op.create_index("ix_team_schedules_team_season", "team_schedules", ["team_name", "season"])
    op.create_index("ix_team_schedules_game_id", "team_schedules", ["game_id"])
    op.create_index("ix_team_schedules_season_week", "team_schedules", ["season", "week"])


def downgrade() -> None:
    op.drop_index("ix_team_schedules_season_week", table_name="team_schedules")
    op.drop_index("ix_team_schedules_game_id", table_name="team_schedules")
    op.drop_index("ix_team_schedules_team_season", table_name="team_schedules")
    op.drop_table("team_schedules")
