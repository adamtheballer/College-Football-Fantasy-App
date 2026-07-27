"""add Saturday Pick 6 contests

Revision ID: 0076_saturday_pick_6
Revises: 0075_processed_waiver_claims
"""

from alembic import op
import sqlalchemy as sa


revision = "0076_saturday_pick_6"
down_revision = "0075_processed_waiver_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saturday_pick_contests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("contest_position", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("lock_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scoring_policy_version", sa.String(length=60), nullable=False),
        sa.Column("sponsor_name", sa.String(length=160)),
        sa.Column("sponsor_logo_url", sa.String(length=500)),
        sa.Column("sponsor_offer_text", sa.String(length=500)),
        sa.Column("sponsor_code", sa.String(length=160)),
        sa.Column("sponsor_url", sa.String(length=500)),
        sa.Column("sponsor_terms", sa.String(length=2000)),
        sa.Column("winning_player_ids_json", sa.JSON()),
        sa.Column("position_overridden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("override_reason", sa.String(length=500)),
        sa.Column("position_override_actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("position_overridden_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("season", "week_number", name="uq_saturday_pick_contest_season_week"),
    )
    op.create_index("ix_saturday_pick_contests_status_lock", "saturday_pick_contests", ["status", "lock_at"])
    op.create_table(
        "saturday_pick_players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contest_id", sa.Integer(), sa.ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("canonical_position", sa.String(length=4), nullable=False),
        sa.Column("player_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("school_snapshot", sa.String(length=200), nullable=False),
        sa.Column("opponent_snapshot", sa.String(length=200), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="SET NULL")),
        sa.Column("game_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("projected_points", sa.Float()),
        sa.Column("final_points", sa.Float()),
        sa.Column("scoring_status", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("contest_id", "player_id", name="uq_saturday_pick_player_contest_player"),
        sa.UniqueConstraint("contest_id", "sort_order", name="uq_saturday_pick_player_contest_sort"),
    )
    op.create_index("ix_saturday_pick_players_contest", "saturday_pick_players", ["contest_id"])
    op.create_table(
        "saturday_pick_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contest_id", sa.Integer(), sa.ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_pick_player_id", sa.Integer(), sa.ForeignKey("saturday_pick_players.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_winner", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("winner_determined_at", sa.DateTime(timezone=True)),
        sa.Column("reward_unlocked_at", sa.DateTime(timezone=True)),
        sa.Column("reward_claimed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("contest_id", "user_id", name="uq_saturday_pick_entry_contest_user"),
    )
    op.create_index("ix_saturday_pick_entries_contest", "saturday_pick_entries", ["contest_id"])
    op.create_index("ix_saturday_pick_entries_user", "saturday_pick_entries", ["user_id"])
    op.create_table(
        "sponsor_reward_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contest_id", sa.Integer(), sa.ForeignKey("saturday_pick_contests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("sponsor_name", sa.String(length=160)),
        sa.Column("placement", sa.String(length=100)),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
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
