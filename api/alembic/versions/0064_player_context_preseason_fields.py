"""Persist source-derived preseason player-context fields.

Revision ID: 0064_player_context_preseason
Revises: 0063_kicker_usage_budget
"""

import sqlalchemy as sa
from alembic import op


revision = "0064_player_context_preseason"
down_revision = "0063_kicker_usage_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("player_season_contexts", sa.Column("depth_position", sa.String(length=20), nullable=True))
    op.add_column(
        "player_season_contexts",
        sa.Column("is_transfer", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "player_season_contexts",
        sa.Column("availability_status", sa.String(length=20), nullable=False, server_default="UNKNOWN"),
    )
    op.add_column(
        "player_season_contexts",
        sa.Column("availability_multiplier", sa.Float(), nullable=False, server_default="0.75"),
    )
    op.add_column(
        "player_season_contexts",
        sa.Column("manual_review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("player_season_contexts", sa.Column("manual_review_reason", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("player_season_contexts", "manual_review_reason")
    op.drop_column("player_season_contexts", "manual_review_required")
    op.drop_column("player_season_contexts", "availability_multiplier")
    op.drop_column("player_season_contexts", "availability_status")
    op.drop_column("player_season_contexts", "is_transfer")
    op.drop_column("player_season_contexts", "depth_position")
