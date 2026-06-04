"""standalone mock draft fields

Revision ID: 0034_standalone_mock_drafts
Revises: 0033_draft_timer_completion
Create Date: 2026-06-03 13:45:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0034_standalone_mock_drafts"
down_revision: str | None = "0033_draft_timer_completion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mock_draft_sessions", sa.Column("host_user_id", sa.Integer(), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("team_count", sa.Integer(), nullable=False, server_default="12"))
    op.add_column("mock_draft_sessions", sa.Column("round_count", sa.Integer(), nullable=False, server_default="13"))
    op.add_column("mock_draft_sessions", sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("intermission_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("intermission_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("current_pick_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("current_pick_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("current_overall_pick", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("mock_draft_sessions", sa.Column("draft_order_locked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("mock_draft_sessions", sa.Column("player_pool", sa.String(length=60), nullable=False, server_default="power4"))
    op.add_column("mock_draft_sessions", sa.Column("scoring_type", sa.String(length=80), nullable=False, server_default="espn_full_ppr"))
    op.add_column("mock_draft_sessions", sa.Column("bot_difficulty", sa.String(length=60), nullable=False, server_default="basic"))
    op.add_column("mock_draft_sessions", sa.Column("history_email_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mock_draft_sessions", sa.Column("should_preserve_history", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_mock_draft_sessions_host_user_id", "mock_draft_sessions", "users", ["host_user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_mock_draft_sessions_host_user_id", "mock_draft_sessions", ["host_user_id"])
    op.create_index("ix_mock_draft_sessions_scheduled_start_at", "mock_draft_sessions", ["scheduled_start_at"])
    op.create_index("ix_mock_draft_sessions_expires_at", "mock_draft_sessions", ["expires_at"])

    op.create_table(
        "mock_draft_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mock_draft_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("team_name", sa.String(length=200), nullable=False),
        sa.Column("participant_type", sa.String(length=30), nullable=False, server_default="human"),
        sa.Column("seat_number", sa.Integer(), nullable=False),
        sa.Column("draft_position", sa.Integer(), nullable=True),
        sa.Column("is_host", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connection_status", sa.String(length=30), nullable=False, server_default="connected"),
        sa.Column("auto_pick_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["mock_draft_id"], ["mock_draft_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mock_draft_id", "draft_position", name="uq_mock_draft_participants_draft_position"),
        sa.UniqueConstraint("mock_draft_id", "seat_number", name="uq_mock_draft_participants_draft_seat"),
        sa.UniqueConstraint("mock_draft_id", "user_id", name="uq_mock_draft_participants_draft_user"),
    )
    op.create_index("ix_mock_draft_participants_mock_draft_id", "mock_draft_participants", ["mock_draft_id"])

    op.add_column("mock_draft_picks", sa.Column("mock_draft_id", sa.Integer(), nullable=True))
    op.add_column("mock_draft_picks", sa.Column("participant_id", sa.Integer(), nullable=True))
    op.add_column("mock_draft_picks", sa.Column("pick_source", sa.String(length=30), nullable=False, server_default="human"))
    op.add_column("mock_draft_picks", sa.Column("auto_pick_reason", sa.String(length=80), nullable=True))
    op.create_foreign_key("fk_mock_draft_picks_mock_draft_id", "mock_draft_picks", "mock_draft_sessions", ["mock_draft_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_mock_draft_picks_participant_id", "mock_draft_picks", "mock_draft_participants", ["participant_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_mock_draft_picks_mock_draft_id", "mock_draft_picks", ["mock_draft_id"])
    op.create_index("ix_mock_draft_picks_participant_id", "mock_draft_picks", ["participant_id"])

    op.add_column("mock_draft_events", sa.Column("mock_draft_id", sa.Integer(), nullable=True))
    op.add_column("mock_draft_events", sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("mock_draft_events", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.add_column("mock_draft_events", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_foreign_key("fk_mock_draft_events_mock_draft_id", "mock_draft_events", "mock_draft_sessions", ["mock_draft_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_mock_draft_events_created_by_user_id", "mock_draft_events", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_mock_draft_events_mock_draft_id", "mock_draft_events", ["mock_draft_id"])


def downgrade() -> None:
    op.drop_index("ix_mock_draft_events_mock_draft_id", table_name="mock_draft_events")
    op.drop_constraint("fk_mock_draft_events_created_by_user_id", "mock_draft_events", type_="foreignkey")
    op.drop_constraint("fk_mock_draft_events_mock_draft_id", "mock_draft_events", type_="foreignkey")
    op.drop_column("mock_draft_events", "created_at")
    op.drop_column("mock_draft_events", "created_by_user_id")
    op.drop_column("mock_draft_events", "payload_json")
    op.drop_column("mock_draft_events", "mock_draft_id")

    op.drop_index("ix_mock_draft_picks_participant_id", table_name="mock_draft_picks")
    op.drop_index("ix_mock_draft_picks_mock_draft_id", table_name="mock_draft_picks")
    op.drop_constraint("fk_mock_draft_picks_participant_id", "mock_draft_picks", type_="foreignkey")
    op.drop_constraint("fk_mock_draft_picks_mock_draft_id", "mock_draft_picks", type_="foreignkey")
    op.drop_column("mock_draft_picks", "auto_pick_reason")
    op.drop_column("mock_draft_picks", "pick_source")
    op.drop_column("mock_draft_picks", "participant_id")
    op.drop_column("mock_draft_picks", "mock_draft_id")

    op.drop_index("ix_mock_draft_participants_mock_draft_id", table_name="mock_draft_participants")
    op.drop_table("mock_draft_participants")

    op.drop_index("ix_mock_draft_sessions_expires_at", table_name="mock_draft_sessions")
    op.drop_index("ix_mock_draft_sessions_scheduled_start_at", table_name="mock_draft_sessions")
    op.drop_index("ix_mock_draft_sessions_host_user_id", table_name="mock_draft_sessions")
    op.drop_constraint("fk_mock_draft_sessions_host_user_id", "mock_draft_sessions", type_="foreignkey")
    for column_name in (
        "should_preserve_history",
        "history_email_sent_at",
        "bot_difficulty",
        "scoring_type",
        "player_pool",
        "draft_order_locked",
        "current_overall_pick",
        "current_pick_expires_at",
        "current_pick_started_at",
        "expires_at",
        "cancelled_at",
        "started_at",
        "intermission_ends_at",
        "intermission_started_at",
        "scheduled_start_at",
        "round_count",
        "team_count",
        "host_user_id",
    ):
        op.drop_column("mock_draft_sessions", column_name)
