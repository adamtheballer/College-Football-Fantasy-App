"""Add durable ESPN scoring reliability controls.

Revision ID: 0113_espn_scoring_reliability
Revises: 0112_trent_mosley_cam_correction
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0113_espn_scoring_reliability"
down_revision: str | None = "0112_trent_mosley_cam_correction"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("provider_game_polls", sa.Column("pending_final_snapshot_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "provider_game_polls",
        sa.Column("pending_final_snapshot_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("provider_game_polls", sa.Column("final_stable_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("provider_game_polls", sa.Column("quarantine_until", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "scoring_alert_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("resource_key", sa.String(length=500), nullable=False, server_default="week"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_emitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider", "season", "week", "code", "resource_key", name="uq_scoring_alert_incidents_scope"),
    )
    op.create_index(
        "ix_scoring_alert_incidents_last_seen",
        "scoring_alert_incidents",
        ["provider", "last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_scoring_alert_incidents_last_seen", table_name="scoring_alert_incidents")
    op.drop_table("scoring_alert_incidents")
    op.drop_column("provider_game_polls", "quarantine_until")
    op.drop_column("provider_game_polls", "final_stable_at")
    op.drop_column("provider_game_polls", "pending_final_snapshot_count")
    op.drop_column("provider_game_polls", "pending_final_snapshot_hash")
