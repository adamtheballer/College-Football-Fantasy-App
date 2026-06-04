"""add mock draft mode and nullable single-player invites

Revision ID: 0036_mock_draft_mode
Revises: 0035_mock_draft_public_invites
Create Date: 2026-06-03 17:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0036_mock_draft_mode"
down_revision: str | None = "0035_mock_draft_public_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mock_draft_sessions",
        sa.Column("mode", sa.String(length=30), nullable=False, server_default="public_multiplayer", quote=True),
    )
    op.create_index(op.f("ix_mock_draft_sessions_mode"), "mock_draft_sessions", ["mode"], unique=False)
    op.alter_column(
        "mock_draft_sessions",
        "invite_code",
        existing_type=sa.String(length=128),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE mock_draft_sessions "
        "SET invite_code = CONCAT('legacy-mock-', id) "
        "WHERE invite_code IS NULL"
    )
    op.alter_column(
        "mock_draft_sessions",
        "invite_code",
        existing_type=sa.String(length=128),
        nullable=False,
    )
    op.drop_index(op.f("ix_mock_draft_sessions_mode"), table_name="mock_draft_sessions")
    op.drop_column("mock_draft_sessions", "mode")
