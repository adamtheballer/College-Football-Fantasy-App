"""add auditable league chat moderation events

Revision ID: 0038_chat_security_audits
Revises: 0037_league_chat_threads
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0038_chat_security_audits"
down_revision: str | Sequence[str] | None = "0037_league_chat_threads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_member_removal_audit_trigger() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION audit_league_member_chat_removal() RETURNS trigger AS $$
            BEGIN
                INSERT INTO chat_audit_events (league_id, action, metadata_json)
                VALUES (
                    OLD.league_id,
                    'league_member_removed',
                    jsonb_build_object('removed_user_id', OLD.user_id)
                );
                RETURN OLD;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_league_members_chat_removal_audit
            AFTER DELETE ON league_members
            FOR EACH ROW EXECUTE FUNCTION audit_league_member_chat_removal();
            """
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER trg_league_members_chat_removal_audit
            AFTER DELETE ON league_members
            BEGIN
                INSERT INTO chat_audit_events (league_id, action, metadata_json)
                VALUES (
                    OLD.league_id,
                    'league_member_removed',
                    json_object('removed_user_id', OLD.user_id)
                );
            END;
            """
        )


def upgrade() -> None:
    op.create_table(
        "chat_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("event_key", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_chat_audit_events_event_key"),
    )
    op.create_index("ix_chat_audit_events_league_created", "chat_audit_events", ["league_id", "created_at", "id"])
    op.create_index("ix_chat_audit_events_action", "chat_audit_events", ["action"])
    _create_member_removal_audit_trigger()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_league_members_chat_removal_audit ON league_members")
        op.execute("DROP FUNCTION IF EXISTS audit_league_member_chat_removal()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_league_members_chat_removal_audit")
    op.drop_index("ix_chat_audit_events_action", table_name="chat_audit_events")
    op.drop_index("ix_chat_audit_events_league_created", table_name="chat_audit_events")
    op.drop_table("chat_audit_events")
