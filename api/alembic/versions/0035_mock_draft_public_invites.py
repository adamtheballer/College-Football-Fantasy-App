"""mock draft public invite token length

Revision ID: 0035_mock_draft_public_invites
Revises: 0034_standalone_mock_drafts
Create Date: 2026-06-03 16:30:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0035_mock_draft_public_invites"
down_revision: str | None = "0034_standalone_mock_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "mock_draft_sessions",
        "invite_code",
        existing_type=sa.String(length=30),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "mock_draft_sessions",
        "invite_code",
        existing_type=sa.String(length=128),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
