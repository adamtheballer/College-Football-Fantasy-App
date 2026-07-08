"""mock draft queue and export metadata

Revision ID: 0036_mock_draft_queue_export
Revises: 0035_draft_clock_events_queue
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0036_mock_draft_queue_export"
down_revision = "0035_draft_clock_events_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mock_drafts") as batch_op:
        batch_op.add_column(sa.Column("cpu_strategy", sa.String(length=40), nullable=False, server_default="rank_position_need"))
        batch_op.add_column(sa.Column("user_team_index", sa.Integer(), nullable=False, server_default="1"))

    op.create_table(
        "mock_draft_queue_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mock_draft_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["mock_draft_id"], ["mock_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mock_draft_id", "player_id", name="uq_mock_draft_queue_player"),
        sa.UniqueConstraint("mock_draft_id", "priority", name="uq_mock_draft_queue_priority"),
    )
    op.create_index("ix_mock_draft_queue_mock_draft_id", "mock_draft_queue_entries", ["mock_draft_id"])


def downgrade() -> None:
    op.drop_index("ix_mock_draft_queue_mock_draft_id", table_name="mock_draft_queue_entries")
    op.drop_table("mock_draft_queue_entries")
    with op.batch_alter_table("mock_drafts") as batch_op:
        batch_op.drop_column("user_team_index")
        batch_op.drop_column("cpu_strategy")
