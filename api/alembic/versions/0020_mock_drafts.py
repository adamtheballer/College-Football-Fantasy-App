"""add isolated mock draft tables

Revision ID: 0020_mock_drafts
Revises: 0019_usernames
Create Date: 2026-07-02 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020_mock_drafts"
down_revision: str | None = "0019_usernames"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mock_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("league_size", sa.Integer(), nullable=False),
        sa.Column("rounds", sa.Integer(), nullable=False),
        sa.Column("current_pick", sa.Integer(), nullable=False),
        sa.Column("settings_json", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_drafts_owner_user_id", "mock_drafts", ["owner_user_id"])
    op.create_index("ix_mock_drafts_status", "mock_drafts", ["status"])

    op.create_table(
        "mock_draft_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mock_draft_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("pick_number", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("round_pick", sa.Integer(), nullable=False),
        sa.Column("team_index", sa.Integer(), nullable=False),
        sa.Column("team_name", sa.String(length=120), nullable=False),
        sa.Column("player_name", sa.String(length=200), nullable=False),
        sa.Column("player_school", sa.String(length=200), nullable=False),
        sa.Column("player_position", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["mock_draft_id"], ["mock_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mock_draft_id", "pick_number", name="uq_mock_draft_picks_mock_pick_number"),
        sa.UniqueConstraint("mock_draft_id", "player_id", name="uq_mock_draft_picks_mock_player"),
    )
    op.create_index("ix_mock_draft_picks_mock_draft_id", "mock_draft_picks", ["mock_draft_id"])
    op.create_index("ix_mock_draft_picks_player_id", "mock_draft_picks", ["player_id"])


def downgrade() -> None:
    op.drop_index("ix_mock_draft_picks_player_id", table_name="mock_draft_picks")
    op.drop_index("ix_mock_draft_picks_mock_draft_id", table_name="mock_draft_picks")
    op.drop_table("mock_draft_picks")
    op.drop_index("ix_mock_drafts_status", table_name="mock_drafts")
    op.drop_index("ix_mock_drafts_owner_user_id", table_name="mock_drafts")
    op.drop_table("mock_drafts")
