"""Add published daily player-popularity snapshots.

Revision ID: 0110_player_popularity
Revises: 0109_saturday_pick_content_audit
"""

import sqlalchemy as sa
from alembic import op


revision = "0110_player_popularity"
down_revision = "0109_saturday_pick_content_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_popularity_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("coverage_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("season", "snapshot_date", name="uq_player_popularity_snapshot_date"),
    )
    op.create_index("ix_player_popularity_snapshots_published", "player_popularity_snapshots", ["season", "status", "published_at"])
    op.create_table(
        "player_popularity_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("player_popularity_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("eligible_league_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rostered_league_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_league_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_sample_league_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("snapshot_id", "player_id", name="uq_player_popularity_metric_snapshot_player"),
    )
    op.create_index("ix_player_popularity_metrics_player", "player_popularity_metrics", ["player_id", "snapshot_id"])
    op.create_table(
        "player_hot_pickup_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("snapshot_id", sa.Integer(), sa.ForeignKey("player_popularity_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("pickup_league_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("snapshot_id", "window_hours", "player_id", name="uq_player_hot_pickup_snapshot_window_player"),
    )
    op.create_index("ix_player_hot_pickup_metrics_window", "player_hot_pickup_metrics", ["snapshot_id", "window_hours", "pickup_league_count"])


def downgrade() -> None:
    op.drop_index("ix_player_hot_pickup_metrics_window", table_name="player_hot_pickup_metrics")
    op.drop_table("player_hot_pickup_metrics")
    op.drop_index("ix_player_popularity_metrics_player", table_name="player_popularity_metrics")
    op.drop_table("player_popularity_metrics")
    op.drop_index("ix_player_popularity_snapshots_published", table_name="player_popularity_snapshots")
    op.drop_table("player_popularity_snapshots")
