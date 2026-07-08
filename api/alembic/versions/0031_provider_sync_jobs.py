"""Add provider sync jobs.

Revision ID: 0031_provider_sync_jobs
Revises: 0030_player_week_score_versions
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0031_provider_sync_jobs"
down_revision: str | None = "0030_player_week_score_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_sync_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("feed", sa.String(length=120), nullable=False),
        sa.Column("season", sa.Integer(), nullable=True),
        sa.Column("week", sa.Integer(), nullable=True),
        sa.Column("scope", sa.String(length=255), server_default="global", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="running", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_inserted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rows_rejected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_summary", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_sync_jobs_provider_feed_week",
        "provider_sync_jobs",
        ["provider", "feed", "season", "week"],
        unique=False,
    )
    op.create_index("ix_provider_sync_jobs_status", "provider_sync_jobs", ["status"], unique=False)
    op.create_index("ix_provider_sync_jobs_started_at", "provider_sync_jobs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_provider_sync_jobs_started_at", table_name="provider_sync_jobs")
    op.drop_index("ix_provider_sync_jobs_status", table_name="provider_sync_jobs")
    op.drop_index("ix_provider_sync_jobs_provider_feed_week", table_name="provider_sync_jobs")
    op.drop_table("provider_sync_jobs")
