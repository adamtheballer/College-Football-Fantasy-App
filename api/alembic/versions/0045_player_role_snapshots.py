"""Add provider-backed player role snapshots for weekly projections.

Revision ID: 0045_player_role_snapshots
Revises: 0044_db_identity
Create Date: 2026-07-17 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0045_player_role_snapshots"
down_revision: str | None = "0044_db_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_role_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("school", sa.String(length=200), nullable=False),
        sa.Column("position", sa.String(length=10), nullable=False),
        sa.Column("depth_order", sa.Integer(), nullable=True),
        sa.Column("role_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("snap_share", sa.Float(), nullable=True),
        sa.Column("route_participation", sa.Float(), nullable=True),
        sa.Column("target_share", sa.Float(), nullable=True),
        sa.Column("carry_share", sa.Float(), nullable=True),
        sa.Column("red_zone_share", sa.Float(), nullable=True),
        sa.Column("goal_line_share", sa.Float(), nullable=True),
        sa.Column("recent_usage_trend", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "season", "week", name="uq_player_role_snapshot_week"),
    )
    op.create_index("ix_player_role_snapshot_player_id", "player_role_snapshots", ["player_id"])
    op.create_index("ix_player_role_snapshot_season_week", "player_role_snapshots", ["season", "week"])
    op.create_index("ix_player_role_snapshot_school_position", "player_role_snapshots", ["school", "position"])


def downgrade() -> None:
    op.drop_index("ix_player_role_snapshot_school_position", table_name="player_role_snapshots")
    op.drop_index("ix_player_role_snapshot_season_week", table_name="player_role_snapshots")
    op.drop_index("ix_player_role_snapshot_player_id", table_name="player_role_snapshots")
    op.drop_table("player_role_snapshots")
