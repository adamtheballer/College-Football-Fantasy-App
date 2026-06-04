"""add draft timer completion fields

Revision ID: 0033_draft_timer_completion
Revises: 0032_multiplayer_game_loop
Create Date: 2026-06-03 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0033_draft_timer_completion"
down_revision: str | None = "0032_multiplayer_game_loop"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("drafts", sa.Column("current_pick_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drafts", sa.Column("current_pick_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drafts", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("drafts", sa.Column("history_email_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("drafts", "history_email_sent_at")
    op.drop_column("drafts", "completed_at")
    op.drop_column("drafts", "current_pick_expires_at")
    op.drop_column("drafts", "current_pick_started_at")
