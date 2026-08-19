"""persist snapshot-keyed live player projections

Revision ID: 0096_live_player_projections
Revises: 0095_player_season_outlooks
"""

from alembic import op
import sqlalchemy as sa


revision = "0096_live_player_projections"
down_revision = "0095_player_season_outlooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_player_projections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("pregame_projection_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("projection_status", sa.String(length=24), nullable=False),
        sa.Column("game_period", sa.Integer(), nullable=True),
        sa.Column("game_clock", sa.String(length=32), nullable=True),
        sa.Column("game_progress", sa.Float(), nullable=True),
        sa.Column("current_stats_json", sa.JSON(), nullable=False),
        sa.Column("projected_final_stats_json", sa.JSON(), nullable=False),
        sa.Column("projected_remaining_stats_json", sa.JSON(), nullable=False),
        sa.Column("projected_remaining_fantasy_points", sa.Float(), nullable=True),
        sa.Column("observability_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("fallback_reason", sa.String(length=120), nullable=True),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pregame_projection_id"], ["weekly_projections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "game_id", "provider_snapshot_hash", name="uq_live_player_projection_snapshot"),
    )
    op.create_index("ix_live_player_projections_week_player", "live_player_projections", ["season", "week", "player_id"])
    op.create_index("ix_live_player_projections_game_snapshot", "live_player_projections", ["game_id", "provider_snapshot_at"])


def downgrade() -> None:
    op.drop_index("ix_live_player_projections_game_snapshot", table_name="live_player_projections")
    op.drop_index("ix_live_player_projections_week_player", table_name="live_player_projections")
    op.drop_table("live_player_projections")
