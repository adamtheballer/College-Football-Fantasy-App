"""Add matchup score versions.

Revision ID: 0032_matchup_score_versions
Revises: 0031_provider_sync_jobs
Create Date: 2026-07-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0032_matchup_score_versions"
down_revision: str | None = "0031_provider_sync_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matchup_score_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("matchup_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("home_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("away_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("scoring_run_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["matchup_id"], ["matchups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scoring_run_id"], ["scoring_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("matchup_id", "version", name="uq_matchup_score_versions_matchup_version"),
    )
    op.create_index("ix_matchup_score_versions_matchup_id", "matchup_score_versions", ["matchup_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_matchup_score_versions_matchup_id", table_name="matchup_score_versions")
    op.drop_table("matchup_score_versions")
