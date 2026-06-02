"""add scheduled league jobs table

Revision ID: 0024_scheduled_league_jobs
Revises: 0023_week_scoring_runs
Create Date: 2026-05-27 00:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0024_scheduled_league_jobs"
down_revision: str | None = "0023_week_scoring_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scheduled_league_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheduled_league_jobs_league_run_state",
        "scheduled_league_jobs",
        ["league_id", "run_at", "status"],
        unique=False,
    )
    op.create_index(
        "ix_scheduled_league_jobs_run_state",
        "scheduled_league_jobs",
        ["run_at", "status"],
        unique=False,
    )
    op.create_index("ix_scheduled_league_jobs_type", "scheduled_league_jobs", ["job_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scheduled_league_jobs_type", table_name="scheduled_league_jobs")
    op.drop_index("ix_scheduled_league_jobs_run_state", table_name="scheduled_league_jobs")
    op.drop_index("ix_scheduled_league_jobs_league_run_state", table_name="scheduled_league_jobs")
    op.drop_table("scheduled_league_jobs")
