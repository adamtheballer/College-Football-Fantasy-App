"""add draft lobby presence and ready tracking

Revision ID: 0029_draft_lobby_presence
Revises: 0028_draft_queue_news
Create Date: 2026-05-29 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0029_draft_lobby_presence"
down_revision: str | None = "0028_draft_queue_news"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft_lobby_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", "team_id", name="uq_draft_lobby_members_draft_team"),
        sa.UniqueConstraint("draft_id", "user_id", name="uq_draft_lobby_members_draft_user"),
    )
    op.create_index("ix_draft_lobby_members_draft_id", "draft_lobby_members", ["draft_id"], unique=False)
    op.create_index("ix_draft_lobby_members_team_id", "draft_lobby_members", ["team_id"], unique=False)
    op.create_index("ix_draft_lobby_members_user_id", "draft_lobby_members", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_draft_lobby_members_user_id", table_name="draft_lobby_members")
    op.drop_index("ix_draft_lobby_members_team_id", table_name="draft_lobby_members")
    op.drop_index("ix_draft_lobby_members_draft_id", table_name="draft_lobby_members")
    op.drop_table("draft_lobby_members")
