"""feature support tables

Revision ID: 0005_feature_support
Revises: 0004_projections
Create Date: 2026-03-07 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_feature_support"
down_revision = "0004_projections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("injuries", sa.Column("injury", sa.String(length=200), nullable=True))
    op.add_column("injuries", sa.Column("return_timeline", sa.String(length=100), nullable=True))

    op.create_table(
        "injury_impacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("delta_fpts", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_injury_impacts_player_id", "injury_impacts", ["player_id"])
    op.create_index("ix_injury_impacts_season_week", "injury_impacts", ["season", "week"])

    op.create_table(
        "defense_vs_position",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("grade", sa.String(length=4), nullable=False, server_default="C"),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="65"),
        sa.Column("yards_per_target", sa.Float(), nullable=False, server_default="7.5"),
        sa.Column("yards_per_rush", sa.Float(), nullable=False, server_default="4.2"),
        sa.Column("pass_td_rate", sa.Float(), nullable=False, server_default="0.04"),
        sa.Column("rush_td_rate", sa.Float(), nullable=False, server_default="0.03"),
        sa.Column("explosive_rate", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("pressure_rate", sa.Float(), nullable=False, server_default="0.22"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_defense_vs_position_team_name", "defense_vs_position", ["team_name"])
    op.create_index("ix_defense_vs_position_season_week", "defense_vs_position", ["season", "week"])
    op.create_index("ix_defense_vs_position_position", "defense_vs_position", ["position"])

    op.create_table(
        "projection_explanations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_projection_explanations_player_season_week"),
    )
    op.create_index("ix_projection_explanations_player_id", "projection_explanations", ["player_id"])
    op.create_index("ix_projection_explanations_season_week", "projection_explanations", ["season", "week"])

    op.create_table(
        "push_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_key", sa.String(length=100), nullable=True),
        sa.Column("device_token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_push_tokens_user_key", "push_tokens", ["user_key"])
    op.create_index("ix_push_tokens_device_token", "push_tokens", ["device_token"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_key", sa.String(length=100), nullable=False),
        sa.Column("injury_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("touchdown_alerts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("usage_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("waiver_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("projection_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("lineup_reminders", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quiet_hours_start", sa.String(length=10), nullable=True),
        sa.Column("quiet_hours_end", sa.String(length=10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_notification_preferences_user_key", "notification_preferences", ["user_key"])

    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_key", sa.String(length=100), nullable=True),
        sa.Column("alert_type", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_logs_user_key", "notification_logs", ["user_key"])
    op.create_index("ix_notification_logs_type", "notification_logs", ["alert_type"])


def downgrade() -> None:
    op.drop_index("ix_notification_logs_type", table_name="notification_logs")
    op.drop_index("ix_notification_logs_user_key", table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index("ix_notification_preferences_user_key", table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.drop_index("ix_push_tokens_device_token", table_name="push_tokens")
    op.drop_index("ix_push_tokens_user_key", table_name="push_tokens")
    op.drop_table("push_tokens")

    op.drop_index("ix_projection_explanations_season_week", table_name="projection_explanations")
    op.drop_index("ix_projection_explanations_player_id", table_name="projection_explanations")
    op.drop_table("projection_explanations")

    op.drop_index("ix_defense_vs_position_position", table_name="defense_vs_position")
    op.drop_index("ix_defense_vs_position_season_week", table_name="defense_vs_position")
    op.drop_index("ix_defense_vs_position_team_name", table_name="defense_vs_position")
    op.drop_table("defense_vs_position")

    op.drop_index("ix_injury_impacts_season_week", table_name="injury_impacts")
    op.drop_index("ix_injury_impacts_player_id", table_name="injury_impacts")
    op.drop_table("injury_impacts")

    op.drop_column("injuries", "return_timeline")
    op.drop_column("injuries", "injury")
