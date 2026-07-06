"""Add scoring worker reliability telemetry and locks.

Revision ID: 0023_scoring_worker_reliability
Revises: 0022_live_scoring_engine
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0023_scoring_worker_reliability"
down_revision: str | None = "0022_live_scoring_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("scoring_runs", sa.Column("provider_latency_ms", sa.Integer(), server_default="0", nullable=False))
    op.add_column("scoring_runs", sa.Column("rows_fetched", sa.Integer(), server_default="0", nullable=False))
    op.add_column("scoring_runs", sa.Column("rows_matched", sa.Integer(), server_default="0", nullable=False))
    op.add_column("scoring_runs", sa.Column("rows_unmatched", sa.Integer(), server_default="0", nullable=False))
    op.add_column("scoring_runs", sa.Column("provider_events_seen", sa.Integer(), server_default="0", nullable=False))
    op.add_column("scoring_runs", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("scoring_runs", sa.Column("data_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scoring_runs", sa.Column("data_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scoring_runs", sa.Column("data_age_seconds", sa.Integer(), nullable=True))
    op.add_column("scoring_runs", sa.Column("lock_key", sa.String(length=255), nullable=True))
    op.add_column("scoring_runs", sa.Column("worker_id", sa.String(length=120), nullable=True))
    op.add_column("scoring_runs", sa.Column("last_successful_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_scoring_runs_last_successful_run_id",
        "scoring_runs",
        "scoring_runs",
        ["last_successful_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "scoring_job_locks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lock_key", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("worker_id", sa.String(length=120), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lock_key", name="uq_scoring_job_locks_lock_key"),
    )
    op.create_index("ix_scoring_job_locks_key", "scoring_job_locks", ["lock_key"])
    op.create_index("ix_scoring_job_locks_status", "scoring_job_locks", ["status"])
    op.create_index("ix_scoring_job_locks_expires_at", "scoring_job_locks", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_scoring_job_locks_expires_at", table_name="scoring_job_locks")
    op.drop_index("ix_scoring_job_locks_status", table_name="scoring_job_locks")
    op.drop_index("ix_scoring_job_locks_key", table_name="scoring_job_locks")
    op.drop_table("scoring_job_locks")

    op.drop_constraint("fk_scoring_runs_last_successful_run_id", "scoring_runs", type_="foreignkey")
    op.drop_column("scoring_runs", "last_successful_run_id")
    op.drop_column("scoring_runs", "worker_id")
    op.drop_column("scoring_runs", "lock_key")
    op.drop_column("scoring_runs", "data_age_seconds")
    op.drop_column("scoring_runs", "data_completed_at")
    op.drop_column("scoring_runs", "data_started_at")
    op.drop_column("scoring_runs", "retry_count")
    op.drop_column("scoring_runs", "provider_events_seen")
    op.drop_column("scoring_runs", "rows_unmatched")
    op.drop_column("scoring_runs", "rows_matched")
    op.drop_column("scoring_runs", "rows_fetched")
    op.drop_column("scoring_runs", "provider_latency_ms")
