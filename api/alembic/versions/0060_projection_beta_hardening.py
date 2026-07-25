"""Add auditable context, ratings, and multipliers for beta projections.

Revision ID: 0060_projection_beta_hardening
Revises: 0059_merge_projection_waiver
Create Date: 2026-07-24 00:00:00.000000
"""

import sqlalchemy as sa
from alembic import op


revision = "0060_projection_beta_hardening"
down_revision = "0059_merge_projection_waiver"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team_season_ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("college_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("offensive_rating", sa.Float(), nullable=True),
        sa.Column("offensive_rank", sa.Integer(), nullable=False),
        sa.Column("offensive_percentile", sa.Float(), nullable=False),
        sa.Column("offense_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("defensive_rating", sa.Float(), nullable=True),
        sa.Column("defensive_rank", sa.Integer(), nullable=False),
        sa.Column("defensive_percentile", sa.Float(), nullable=False),
        sa.Column("opponent_defense_multiplier", sa.Float(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=100), nullable=False, server_default="manual_import"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.UniqueConstraint("team_id", "season", name="uq_team_season_ratings_team_season"),
    )
    op.create_index("ix_team_season_ratings_season", "team_season_ratings", ["season"])
    op.create_table(
        "player_season_contexts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("current_team_id", sa.Integer(), sa.ForeignKey("college_teams.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("historical_team_name", sa.String(length=200), nullable=True),
        sa.Column("current_team_verification_status", sa.String(length=40), nullable=False, server_default="legacy_player_record"),
        sa.Column("identity_source", sa.String(length=100), nullable=False, server_default="player.school"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("role_score", sa.Float(), nullable=True),
        sa.Column("role_confidence", sa.Float(), nullable=True),
        sa.Column("manual_review_status", sa.String(length=40), nullable=False, server_default="unreviewed"),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.UniqueConstraint("player_id", "season", name="uq_player_season_contexts_player_season"),
    )
    op.create_index("ix_player_season_contexts_team_season", "player_season_contexts", ["current_team_id", "season"])
    op.create_index("ix_player_season_contexts_season_active", "player_season_contexts", ["season", "is_active"])

    op.add_column("usage_shares", sa.Column("pass_share", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("prior_rush_share", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("prior_target_share", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("projected_rush_share", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("projected_target_share", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("pre_normalization_role_score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("usage_shares", sa.Column("raw_usage_multiplier", sa.Float(), nullable=False, server_default="1"))
    op.add_column("usage_shares", sa.Column("usage_confidence", sa.Float(), nullable=False, server_default="0.5"))
    op.add_column("usage_shares", sa.Column("applied_usage_multiplier", sa.Float(), nullable=False, server_default="1"))
    op.add_column("usage_shares", sa.Column("fallback_method", sa.String(length=100), nullable=True))
    op.add_column("usage_shares", sa.Column("adjustment_reason", sa.String(length=500), nullable=True))

    op.add_column("weekly_projections", sa.Column("team_id", sa.Integer(), sa.ForeignKey("college_teams.id", ondelete="SET NULL"), nullable=True))
    op.add_column("weekly_projections", sa.Column("opponent_team_id", sa.Integer(), sa.ForeignKey("college_teams.id", ondelete="SET NULL"), nullable=True))
    op.add_column("weekly_projections", sa.Column("projection_status", sa.String(length=20), nullable=False, server_default="ACTIVE"))
    op.add_column("weekly_projections", sa.Column("availability_multiplier", sa.Float(), nullable=False, server_default="1"))
    op.add_column("weekly_projections", sa.Column("usage_multiplier", sa.Float(), nullable=False, server_default="1"))
    op.add_column("weekly_projections", sa.Column("offense_multiplier", sa.Float(), nullable=False, server_default="1"))
    op.add_column("weekly_projections", sa.Column("opponent_defense_multiplier", sa.Float(), nullable=False, server_default="1"))
    op.add_column("weekly_projections", sa.Column("confidence", sa.Float(), nullable=False, server_default="0"))
    op.add_column("weekly_projections", sa.Column("fallback_reason", sa.String(length=500), nullable=True))
    op.add_column("weekly_projections", sa.Column("model_version", sa.String(length=50), nullable=False, server_default="v3_beta"))


def downgrade() -> None:
    for column in (
        "model_version", "fallback_reason", "confidence", "opponent_defense_multiplier", "offense_multiplier",
        "usage_multiplier", "availability_multiplier", "projection_status", "opponent_team_id", "team_id",
    ):
        op.drop_column("weekly_projections", column)
    for column in (
        "adjustment_reason", "fallback_method", "applied_usage_multiplier", "usage_confidence", "raw_usage_multiplier",
        "pre_normalization_role_score", "projected_target_share", "projected_rush_share", "prior_target_share",
        "prior_rush_share", "pass_share",
    ):
        op.drop_column("usage_shares", column)
    op.drop_index("ix_player_season_contexts_season_active", table_name="player_season_contexts")
    op.drop_index("ix_player_season_contexts_team_season", table_name="player_season_contexts")
    op.drop_table("player_season_contexts")
    op.drop_index("ix_team_season_ratings_season", table_name="team_season_ratings")
    op.drop_table("team_season_ratings")
