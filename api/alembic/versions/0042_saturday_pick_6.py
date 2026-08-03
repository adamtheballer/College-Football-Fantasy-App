"""Add persisted Saturday Pick 6 contest and entry state.

Revision ID: 0042_saturday_pick_6
Revises: 0041_score_compat
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0042_saturday_pick_6"
down_revision: str | None = "0041_score_compat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saturday_pick_contests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False, server_default="Saturday Pick 6"),
        sa.Column("contest_position", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="DRAFT"),
        sa.Column("lock_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scoring_policy_version", sa.String(length=64), nullable=False, server_default="STANDARD_V1"),
        sa.Column("winning_player_ids_json", sa.JSON(), nullable=True),
        sa.Column("sponsor_name", sa.String(length=160), nullable=True),
        sa.Column("sponsor_logo_url", sa.String(length=500), nullable=True),
        sa.Column("sponsor_offer_text", sa.String(length=500), nullable=True),
        sa.Column("sponsor_code", sa.String(length=160), nullable=True),
        sa.Column("sponsor_url", sa.String(length=500), nullable=True),
        sa.Column("sponsor_terms", sa.String(length=1000), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("season", "week_number", name="uq_saturday_pick_contest_season_week"),
    )
    op.create_index("ix_saturday_pick_contests_status_lock", "saturday_pick_contests", ["status", "lock_at"])

    op.create_table(
        "saturday_pick_players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("canonical_position", sa.String(length=8), nullable=False),
        sa.Column("player_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("school_snapshot", sa.String(length=200), nullable=False),
        sa.Column("opponent_snapshot", sa.String(length=200), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("game_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("projected_points", sa.Float(), nullable=True),
        sa.Column("live_points", sa.Float(), nullable=True),
        sa.Column("final_points", sa.Float(), nullable=True),
        sa.Column("scoring_status", sa.String(length=32), nullable=False, server_default="NOT_STARTED"),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["contest_id"], ["saturday_pick_contests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contest_id", "player_id", name="uq_saturday_pick_player_contest_player"),
        sa.UniqueConstraint("contest_id", "sort_order", name="uq_saturday_pick_player_contest_sort_order"),
    )
    op.create_index("ix_saturday_pick_players_contest", "saturday_pick_players", ["contest_id"])

    op.create_table(
        "saturday_pick_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("selected_pick_player_id", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_winner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reward_unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["contest_id"], ["saturday_pick_contests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["selected_pick_player_id"], ["saturday_pick_players.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contest_id", "user_id", name="uq_saturday_pick_entry_contest_user"),
    )
    op.create_index("ix_saturday_pick_entries_contest", "saturday_pick_entries", ["contest_id"])
    op.create_index("ix_saturday_pick_entries_user", "saturday_pick_entries", ["user_id"])

    op.create_table(
        "sponsor_reward_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contest_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("sponsor_name", sa.String(length=160), nullable=False),
        sa.Column("placement", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["contest_id"], ["saturday_pick_contests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sponsor_reward_events_contest_user", "sponsor_reward_events", ["contest_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_sponsor_reward_events_contest_user", table_name="sponsor_reward_events")
    op.drop_table("sponsor_reward_events")
    op.drop_index("ix_saturday_pick_entries_user", table_name="saturday_pick_entries")
    op.drop_index("ix_saturday_pick_entries_contest", table_name="saturday_pick_entries")
    op.drop_table("saturday_pick_entries")
    op.drop_index("ix_saturday_pick_players_contest", table_name="saturday_pick_players")
    op.drop_table("saturday_pick_players")
    op.drop_index("ix_saturday_pick_contests_status_lock", table_name="saturday_pick_contests")
    op.drop_table("saturday_pick_contests")
