"""Persist carried-forward weekly context, reviewed events, and projection snapshots.

Revision ID: 0065_weekly_projection_pipeline
Revises: 0064_player_context_preseason
"""

import sqlalchemy as sa
from alembic import op


revision = "0065_weekly_projection_pipeline"
down_revision = "0064_player_context_preseason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_availability_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("probability_active", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("availability_multiplier", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("snap_limit", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("source_reliability", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_from_week", sa.Integer(), nullable=False),
        sa.Column("effective_until_week", sa.Integer(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_player_availability_events_player_season_week",
        "player_availability_events",
        ["player_id", "season", "week"],
    )
    op.create_index(
        "ix_player_availability_events_effective_window",
        "player_availability_events",
        ["season", "effective_from_week", "effective_until_week"],
    )
    op.create_table(
        "player_news_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("related_player_id", sa.Integer(), nullable=True),
        sa.Column("current_team_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=True),
        sa.Column("usage_direction", sa.String(length=20), nullable=True),
        sa.Column("role_score_delta", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("source_reliability", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_from_week", sa.Integer(), nullable=False),
        sa.Column("effective_until_week", sa.Integer(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_player_id"], ["players.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_team_id"], ["college_teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_player_news_events_player_season_week", "player_news_events", ["player_id", "season", "week"])
    op.create_index(
        "ix_player_news_events_effective_window",
        "player_news_events",
        ["season", "effective_from_week", "effective_until_week"],
    )
    op.create_table(
        "player_weekly_contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("current_team_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=40), nullable=True),
        sa.Column("role_score", sa.Float(), nullable=True),
        sa.Column("projected_usage_share", sa.Float(), nullable=True),
        sa.Column("usage_confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("availability_status", sa.String(length=20), nullable=False, server_default="UNKNOWN"),
        sa.Column("availability_multiplier", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("availability_event_id", sa.Integer(), nullable=True),
        sa.Column("news_event_id", sa.Integer(), nullable=True),
        sa.Column("source_context_week", sa.Integer(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manual_review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("change_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["availability_event_id"], ["player_availability_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_team_id"], ["college_teams.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["news_event_id"], ["player_news_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_player_weekly_contexts_player_season_week"),
    )
    op.create_index("ix_player_weekly_contexts_season_week", "player_weekly_contexts", ["season", "week"])
    op.create_index(
        "ix_player_weekly_contexts_team_season_week",
        "player_weekly_contexts",
        ["current_team_id", "season", "week"],
    )

    op.add_column(
        "weekly_projections",
        sa.Column("projection_version", sa.String(length=20), nullable=False, server_default="FINAL"),
    )
    op.add_column(
        "weekly_projections",
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("weekly_projections", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("uq_weekly_projections_player_season_week", "weekly_projections", type_="unique")
    op.create_unique_constraint(
        "uq_weekly_projections_player_season_week_version",
        "weekly_projections",
        ["player_id", "season", "week", "projection_version"],
    )

    op.add_column("usage_shares", sa.Column("projection_version", sa.String(length=20), nullable=False, server_default="FINAL"))
    op.add_column(
        "projection_inputs_audit",
        sa.Column("projection_version", sa.String(length=20), nullable=False, server_default="FINAL"),
    )
    op.drop_constraint("uq_projection_inputs_player_season_week", "projection_inputs_audit", type_="unique")
    op.create_unique_constraint(
        "uq_projection_inputs_player_season_week_version",
        "projection_inputs_audit",
        ["player_id", "season", "week", "projection_version"],
    )
    op.add_column(
        "projection_explanations",
        sa.Column("projection_version", sa.String(length=20), nullable=False, server_default="FINAL"),
    )
    op.drop_constraint("uq_projection_explanations_player_season_week", "projection_explanations", type_="unique")
    op.create_unique_constraint(
        "uq_projection_explanations_player_season_week_version",
        "projection_explanations",
        ["player_id", "season", "week", "projection_version"],
    )
    op.add_column("player_stats", sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("player_stats", "verified")
    op.drop_constraint("uq_projection_explanations_player_season_week_version", "projection_explanations", type_="unique")
    op.drop_column("projection_explanations", "projection_version")
    op.create_unique_constraint(
        "uq_projection_explanations_player_season_week", "projection_explanations", ["player_id", "season", "week"]
    )
    op.drop_constraint("uq_projection_inputs_player_season_week_version", "projection_inputs_audit", type_="unique")
    op.drop_column("projection_inputs_audit", "projection_version")
    op.create_unique_constraint(
        "uq_projection_inputs_player_season_week", "projection_inputs_audit", ["player_id", "season", "week"]
    )
    op.drop_column("usage_shares", "projection_version")
    op.drop_constraint("uq_weekly_projections_player_season_week_version", "weekly_projections", type_="unique")
    op.drop_column("weekly_projections", "locked_at")
    op.drop_column("weekly_projections", "is_published")
    op.drop_column("weekly_projections", "projection_version")
    op.create_unique_constraint(
        "uq_weekly_projections_player_season_week", "weekly_projections", ["player_id", "season", "week"]
    )
    op.drop_index("ix_player_weekly_contexts_team_season_week", table_name="player_weekly_contexts")
    op.drop_index("ix_player_weekly_contexts_season_week", table_name="player_weekly_contexts")
    op.drop_table("player_weekly_contexts")
    op.drop_index("ix_player_news_events_effective_window", table_name="player_news_events")
    op.drop_index("ix_player_news_events_player_season_week", table_name="player_news_events")
    op.drop_table("player_news_events")
    op.drop_index("ix_player_availability_events_effective_window", table_name="player_availability_events")
    op.drop_index("ix_player_availability_events_player_season_week", table_name="player_availability_events")
    op.drop_table("player_availability_events")
