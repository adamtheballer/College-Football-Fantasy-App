"""draft clock events and queue

Revision ID: 0035_draft_clock_events_queue
Revises: 0034_roster_idempotency_lineup_events
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0035_draft_clock_events_queue"
down_revision = "0034_roster_idempotency_lineup_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("drafts") as batch_op:
        batch_op.add_column(sa.Column("pick_started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("pick_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("clock_seconds", sa.Integer(), nullable=False, server_default="90"))
        batch_op.add_column(sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("pause_accumulated_seconds", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("autopick_strategy", sa.String(length=40), nullable=False, server_default="best_available")
        )

    op.execute("UPDATE drafts SET clock_seconds = pick_timer_seconds WHERE clock_seconds = 90")

    op.create_table(
        "draft_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_draft_events_draft_id", "draft_events", ["draft_id"])
    op.create_index("ix_draft_events_league_id", "draft_events", ["league_id"])
    op.create_index("ix_draft_events_event_type", "draft_events", ["event_type"])

    op.create_table(
        "draft_queue_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("draft_id", "team_id", "player_id", name="uq_draft_queue_team_player"),
        sa.UniqueConstraint("draft_id", "team_id", "priority", name="uq_draft_queue_team_priority"),
    )
    op.create_index("ix_draft_queue_entries_draft_team", "draft_queue_entries", ["draft_id", "team_id"])


def downgrade() -> None:
    op.drop_index("ix_draft_queue_entries_draft_team", table_name="draft_queue_entries")
    op.drop_table("draft_queue_entries")

    op.drop_index("ix_draft_events_event_type", table_name="draft_events")
    op.drop_index("ix_draft_events_league_id", table_name="draft_events")
    op.drop_index("ix_draft_events_draft_id", table_name="draft_events")
    op.drop_table("draft_events")

    with op.batch_alter_table("drafts") as batch_op:
        batch_op.drop_column("autopick_strategy")
        batch_op.drop_column("pause_accumulated_seconds")
        batch_op.drop_column("paused_at")
        batch_op.drop_column("clock_seconds")
        batch_op.drop_column("pick_expires_at")
        batch_op.drop_column("pick_started_at")
