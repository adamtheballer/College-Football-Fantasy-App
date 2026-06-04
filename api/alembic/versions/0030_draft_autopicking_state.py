"""add draft timer auto-picking state fields

Revision ID: 0030_draft_autopicking_state
Revises: 0029_draft_lobby_presence
Create Date: 2026-06-01 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0030_draft_autopicking_state"
down_revision: str | None = "0029_draft_lobby_presence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "draft_timer_states",
        sa.Column("auto_picking_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "draft_timer_states",
        sa.Column("auto_picking_pick_number", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("draft_timer_states", "auto_picking_pick_number")
    op.drop_column("draft_timer_states", "auto_picking_started_at")
