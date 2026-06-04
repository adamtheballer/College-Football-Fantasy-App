"""add isolated mock draft multiplayer tables

Revision ID: 0031_mock_draft_mp
Revises: 0030_draft_autopicking_state
Create Date: 2026-06-02 00:00:01.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0031_mock_draft_mp"
down_revision: str | None = "0030_draft_autopicking_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mock_draft_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("commissioner_user_id", sa.Integer(), nullable=False),
        sa.Column("invite_code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("manager_count", sa.Integer(), nullable=False),
        sa.Column("draft_type", sa.String(length=30), nullable=False),
        sa.Column("pick_timer_seconds", sa.Integer(), nullable=False),
        sa.Column("roster_slots_json", sa.JSON(), nullable=False),
        sa.Column("scoring_json", sa.JSON(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("draft_datetime_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["commissioner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mock_draft_sessions_commissioner_user_id"), "mock_draft_sessions", ["commissioner_user_id"], unique=False)
    op.create_index(op.f("ix_mock_draft_sessions_invite_code"), "mock_draft_sessions", ["invite_code"], unique=True)
    op.create_index(op.f("ix_mock_draft_sessions_status"), "mock_draft_sessions", ["status"], unique=False)

    op.create_table(
        "mock_draft_seats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seat_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("is_cpu", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "owner_user_id", name="uq_mock_draft_seats_session_owner"),
        sa.UniqueConstraint("session_id", "seat_number", name="uq_mock_draft_seats_session_seat_number"),
    )
    op.create_index("ix_mock_draft_seats_session_id", "mock_draft_seats", ["session_id"], unique=False)

    op.create_table(
        "mock_draft_picks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seat_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("made_by_user_id", sa.Integer(), nullable=True),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("round_pick", sa.Integer(), nullable=False),
        sa.Column("overall_pick", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["made_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seat_id"], ["mock_draft_seats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_mock_draft_picks_session_idempotency_key"),
        sa.UniqueConstraint("session_id", "overall_pick", name="uq_mock_draft_picks_session_overall_pick"),
        sa.UniqueConstraint("session_id", "player_id", name="uq_mock_draft_picks_session_player"),
    )
    op.create_index("ix_mock_draft_picks_player_id", "mock_draft_picks", ["player_id"], unique=False)
    op.create_index("ix_mock_draft_picks_seat_id", "mock_draft_picks", ["seat_id"], unique=False)
    op.create_index("ix_mock_draft_picks_session_id", "mock_draft_picks", ["session_id"], unique=False)

    op.create_table(
        "mock_draft_roster_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seat_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seat_id"], ["mock_draft_seats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("seat_id", "player_id", name="uq_mock_draft_roster_seat_player"),
        sa.UniqueConstraint("session_id", "player_id", name="uq_mock_draft_roster_session_player"),
    )
    op.create_index("ix_mock_draft_roster_entries_player_id", "mock_draft_roster_entries", ["player_id"], unique=False)
    op.create_index("ix_mock_draft_roster_entries_seat_id", "mock_draft_roster_entries", ["seat_id"], unique=False)
    op.create_index("ix_mock_draft_roster_entries_session_id", "mock_draft_roster_entries", ["session_id"], unique=False)

    op.create_table(
        "mock_draft_lobby_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seat_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_ready", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["seat_id"], ["mock_draft_seats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seat_id", name="uq_mock_draft_lobby_members_session_seat"),
        sa.UniqueConstraint("session_id", "user_id", name="uq_mock_draft_lobby_members_session_user"),
    )
    op.create_index("ix_mock_draft_lobby_members_seat_id", "mock_draft_lobby_members", ["seat_id"], unique=False)
    op.create_index("ix_mock_draft_lobby_members_session_id", "mock_draft_lobby_members", ["session_id"], unique=False)
    op.create_index("ix_mock_draft_lobby_members_user_id", "mock_draft_lobby_members", ["user_id"], unique=False)

    op.create_table(
        "mock_draft_timer_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("timer_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_total_seconds", sa.Integer(), nullable=False),
        sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_picking_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_picking_pick_number", sa.Integer(), nullable=True),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_mock_draft_timer_states_session_id"),
    )
    op.create_index("ix_mock_draft_timer_states_session_id", "mock_draft_timer_states", ["session_id"], unique=False)

    op.create_table(
        "mock_draft_queue_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("seat_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seat_id"], ["mock_draft_seats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seat_id", "player_id", name="uq_mock_draft_queue_items_unique_player"),
        sa.UniqueConstraint("session_id", "seat_id", "priority", name="uq_mock_draft_queue_items_unique_priority"),
    )
    op.create_index("ix_mock_draft_queue_items_session_player", "mock_draft_queue_items", ["session_id", "player_id"], unique=False)
    op.create_index("ix_mock_draft_queue_items_session_seat_priority", "mock_draft_queue_items", ["session_id", "seat_id", "priority"], unique=False)

    op.create_table(
        "mock_draft_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mock_draft_events_event_type", "mock_draft_events", ["event_type"], unique=False)
    op.create_index("ix_mock_draft_events_session_id_id", "mock_draft_events", ["session_id", "id"], unique=False)
    op.create_index("ix_mock_draft_events_session_id_occurred_at", "mock_draft_events", ["session_id", "occurred_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mock_draft_events_session_id_occurred_at", table_name="mock_draft_events")
    op.drop_index("ix_mock_draft_events_session_id_id", table_name="mock_draft_events")
    op.drop_index("ix_mock_draft_events_event_type", table_name="mock_draft_events")
    op.drop_table("mock_draft_events")
    op.drop_index("ix_mock_draft_queue_items_session_seat_priority", table_name="mock_draft_queue_items")
    op.drop_index("ix_mock_draft_queue_items_session_player", table_name="mock_draft_queue_items")
    op.drop_table("mock_draft_queue_items")
    op.drop_index("ix_mock_draft_timer_states_session_id", table_name="mock_draft_timer_states")
    op.drop_table("mock_draft_timer_states")
    op.drop_index("ix_mock_draft_lobby_members_user_id", table_name="mock_draft_lobby_members")
    op.drop_index("ix_mock_draft_lobby_members_session_id", table_name="mock_draft_lobby_members")
    op.drop_index("ix_mock_draft_lobby_members_seat_id", table_name="mock_draft_lobby_members")
    op.drop_table("mock_draft_lobby_members")
    op.drop_index("ix_mock_draft_roster_entries_session_id", table_name="mock_draft_roster_entries")
    op.drop_index("ix_mock_draft_roster_entries_seat_id", table_name="mock_draft_roster_entries")
    op.drop_index("ix_mock_draft_roster_entries_player_id", table_name="mock_draft_roster_entries")
    op.drop_table("mock_draft_roster_entries")
    op.drop_index("ix_mock_draft_picks_session_id", table_name="mock_draft_picks")
    op.drop_index("ix_mock_draft_picks_seat_id", table_name="mock_draft_picks")
    op.drop_index("ix_mock_draft_picks_player_id", table_name="mock_draft_picks")
    op.drop_table("mock_draft_picks")
    op.drop_index("ix_mock_draft_seats_session_id", table_name="mock_draft_seats")
    op.drop_table("mock_draft_seats")
    op.drop_index(op.f("ix_mock_draft_sessions_status"), table_name="mock_draft_sessions")
    op.drop_index(op.f("ix_mock_draft_sessions_invite_code"), table_name="mock_draft_sessions")
    op.drop_index(op.f("ix_mock_draft_sessions_commissioner_user_id"), table_name="mock_draft_sessions")
    op.drop_table("mock_draft_sessions")
