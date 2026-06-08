"""allow standalone mock draft picks without seats

Revision ID: 0038_nullable_mock_pick_seat
Revises: 0037_news_wire
Create Date: 2026-06-06 22:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0038_nullable_mock_pick_seat"
down_revision: str | None = "0037_news_wire"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mock_draft_picks") as batch_op:
        batch_op.alter_column("seat_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("mock_draft_picks") as batch_op:
        batch_op.alter_column("seat_id", existing_type=sa.Integer(), nullable=False)
