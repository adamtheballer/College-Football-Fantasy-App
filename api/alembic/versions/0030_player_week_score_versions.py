"""Add player week score version metadata.

Revision ID: 0030_player_week_score_versions
Revises: 0029_audit_events
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0030_player_week_score_versions"
down_revision: str | None = "0029_audit_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("player_week_scores", sa.Column("stat_version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("player_week_scores", sa.Column("source_provider", sa.String(length=50), nullable=True))
    op.add_column("player_week_scores", sa.Column("source_event_id", sa.String(length=120), nullable=True))
    op.add_column("player_week_scores", sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("player_week_scores", sa.Column("calculation_version", sa.String(length=50), server_default="2026.1", nullable=False))
    op.add_column("player_week_scores", sa.Column("previous_score", sa.Float(), nullable=True))
    op.add_column("player_week_scores", sa.Column("correction_delta", sa.Float(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("player_week_scores", "correction_delta")
    op.drop_column("player_week_scores", "previous_score")
    op.drop_column("player_week_scores", "calculation_version")
    op.drop_column("player_week_scores", "source_updated_at")
    op.drop_column("player_week_scores", "source_event_id")
    op.drop_column("player_week_scores", "source_provider")
    op.drop_column("player_week_scores", "stat_version")
