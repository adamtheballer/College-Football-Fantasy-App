"""add worker heartbeat telemetry

Revision ID: 0036_worker_heartbeats
Revises: 0035_release_hardening_settings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0036_worker_health"
down_revision: str | Sequence[str] | None = "0035_release_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("worker_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_heartbeats_worker_name", "worker_heartbeats", ["worker_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeats_worker_name", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
