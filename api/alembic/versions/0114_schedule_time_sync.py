"""Add canonical schedule-time provenance and review issues.

Revision ID: 0114_schedule_time_sync
Revises: 0113_espn_scoring_reliability
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0114_schedule_time_sync"
down_revision: str | None = "0113_espn_scoring_reliability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("team_schedules", sa.Column("time_status", sa.String(length=32), nullable=False, server_default="tbd"))
    op.add_column("team_schedules", sa.Column("schedule_source", sa.String(length=64), nullable=True))
    op.add_column("team_schedules", sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("team_schedules", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("team_schedules", sa.Column("schedule_confidence", sa.Float(), nullable=True))
    op.add_column("team_schedules", sa.Column("manual_override", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("team_schedules", sa.Column("manual_override_reason", sa.String(length=1000), nullable=True))
    op.execute("UPDATE team_schedules SET time_status = CASE WHEN kickoff_at IS NULL THEN 'tbd' ELSE 'confirmed' END")
    op.execute("UPDATE team_schedules SET schedule_source = 'sheet_seed' WHERE schedule_source IS NULL")
    op.create_table(
        "schedule_sync_issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("opponent_name", sa.String(length=200), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("current_value", sa.String(length=500), nullable=True),
        sa.Column("provider_value", sa.String(length=500), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_schedule_sync_issues_scope", "schedule_sync_issues", ["season", "week", "issue_type"])
    op.create_index("ix_schedule_sync_issues_open", "schedule_sync_issues", ["resolved_at"])


def downgrade() -> None:
    op.drop_index("ix_schedule_sync_issues_open", table_name="schedule_sync_issues")
    op.drop_index("ix_schedule_sync_issues_scope", table_name="schedule_sync_issues")
    op.drop_table("schedule_sync_issues")
    op.drop_column("team_schedules", "manual_override_reason")
    op.drop_column("team_schedules", "manual_override")
    op.drop_column("team_schedules", "schedule_confidence")
    op.drop_column("team_schedules", "last_synced_at")
    op.drop_column("team_schedules", "source_updated_at")
    op.drop_column("team_schedules", "schedule_source")
    op.drop_column("team_schedules", "time_status")
