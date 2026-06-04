"""add scoring runs table

Revision ID: 0023_week_scoring_runs
Revises: 0022_waiver_claim_engine
Create Date: 2026-05-26 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0023_week_scoring_runs"
down_revision: str | None = "0022_waiver_claim_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scoring_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("source_mode", sa.String(length=40), nullable=False, server_default="actual_then_projection"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("finalize_matchups", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("finalized_week_state", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scoring_runs_league_week", "scoring_runs", ["league_id", "season", "week"], unique=False)
    op.create_index("ix_scoring_runs_status", "scoring_runs", ["status"], unique=False)
    op.create_index("ix_scoring_runs_created_at", "scoring_runs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scoring_runs_created_at", table_name="scoring_runs")
    op.drop_index("ix_scoring_runs_status", table_name="scoring_runs")
    op.drop_index("ix_scoring_runs_league_week", table_name="scoring_runs")
    op.drop_table("scoring_runs")
