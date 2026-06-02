"""add draft queue persistence and player news snapshots

Revision ID: 0028_draft_queue_news
Revises: 0027_push_token_text_for_webpush
Create Date: 2026-05-28 10:15:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0028_draft_queue_news"
down_revision: str | None = "0027_push_token_text_for_webpush"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "draft_team_queue_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "draft_id",
            "team_id",
            "player_id",
            name="uq_draft_team_queue_items_unique_player",
        ),
        sa.UniqueConstraint(
            "draft_id",
            "team_id",
            "priority",
            name="uq_draft_team_queue_items_unique_priority",
        ),
    )
    op.create_index(
        "ix_draft_team_queue_items_draft_team_priority",
        "draft_team_queue_items",
        ["draft_id", "team_id", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_draft_team_queue_items_draft_player",
        "draft_team_queue_items",
        ["draft_id", "player_id"],
        unique=False,
    )

    op.create_table(
        "player_news_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(length=1200), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="verified_override"),
        sa.Column("is_transfer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("from_school", sa.String(length=120), nullable=True),
        sa.Column("to_school", sa.String(length=120), nullable=True),
        sa.Column("expected_role", sa.String(length=255), nullable=True),
        sa.Column("source_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", "season", name="uq_player_news_snapshots_player_season"),
    )
    op.create_index("ix_player_news_snapshots_player_id", "player_news_snapshots", ["player_id"], unique=False)
    op.create_index("ix_player_news_snapshots_season", "player_news_snapshots", ["season"], unique=False)
    op.create_index("ix_player_news_snapshots_verified", "player_news_snapshots", ["verified_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_player_news_snapshots_verified", table_name="player_news_snapshots")
    op.drop_index("ix_player_news_snapshots_season", table_name="player_news_snapshots")
    op.drop_index("ix_player_news_snapshots_player_id", table_name="player_news_snapshots")
    op.drop_table("player_news_snapshots")

    op.drop_index("ix_draft_team_queue_items_draft_player", table_name="draft_team_queue_items")
    op.drop_index("ix_draft_team_queue_items_draft_team_priority", table_name="draft_team_queue_items")
    op.drop_table("draft_team_queue_items")
