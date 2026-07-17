"""migrate league activity messages into thread-based league chat

Revision ID: 0037_league_chat_threads
Revises: 0036_worker_health
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0037_league_chat_threads"
down_revision: str | Sequence[str] | None = "0036_worker_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CHAT_MESSAGE_TYPES = {
    "user",
    "system",
    "trade_finalized",
    "trade_processed",
    "waiver",
    "draft",
    "commissioner",
}


def _mapped_legacy_message_type(message_type: str | None) -> str:
    normalized = (message_type or "system").lower()
    if normalized in _CHAT_MESSAGE_TYPES:
        return normalized
    if normalized == "trade":
        return "trade_processed"
    return "system"


def _create_reply_thread_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION enforce_chat_message_reply_thread() RETURNS trigger AS $$
            BEGIN
                IF NEW.reply_to_message_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1
                    FROM chat_messages parent_message
                    WHERE parent_message.id = NEW.reply_to_message_id
                      AND parent_message.thread_id = NEW.thread_id
                ) THEN
                    RAISE EXCEPTION 'chat message replies must remain in the same thread';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_chat_messages_reply_thread
            BEFORE INSERT OR UPDATE OF thread_id, reply_to_message_id ON chat_messages
            FOR EACH ROW EXECUTE FUNCTION enforce_chat_message_reply_thread();
            """
        )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER trg_chat_messages_reply_thread_insert
            BEFORE INSERT ON chat_messages
            WHEN NEW.reply_to_message_id IS NOT NULL
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM chat_messages parent_message
                    WHERE parent_message.id = NEW.reply_to_message_id
                      AND parent_message.thread_id = NEW.thread_id
                ) THEN RAISE(ABORT, 'chat message replies must remain in the same thread') END;
            END;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_chat_messages_reply_thread_update
            BEFORE UPDATE OF thread_id, reply_to_message_id ON chat_messages
            WHEN NEW.reply_to_message_id IS NOT NULL
            BEGIN
                SELECT CASE WHEN NOT EXISTS (
                    SELECT 1 FROM chat_messages parent_message
                    WHERE parent_message.id = NEW.reply_to_message_id
                      AND parent_message.thread_id = NEW.thread_id
                ) THEN RAISE(ABORT, 'chat message replies must remain in the same thread') END;
            END;
            """
        )


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("thread_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("direct_user_low_id", sa.Integer(), nullable=True),
        sa.Column("direct_user_high_id", sa.Integer(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("thread_type IN ('league', 'direct')", name="ck_chat_threads_type"),
        sa.CheckConstraint(
            "(thread_type = 'league' AND direct_user_low_id IS NULL AND direct_user_high_id IS NULL) OR "
            "(thread_type = 'direct' AND direct_user_low_id IS NOT NULL AND direct_user_high_id IS NOT NULL "
            "AND direct_user_low_id < direct_user_high_id)",
            name="ck_chat_threads_shape",
        ),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["direct_user_low_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["direct_user_high_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "league_id", name="uq_chat_threads_id_league"),
        sa.UniqueConstraint(
            "league_id",
            "direct_user_low_id",
            "direct_user_high_id",
            "thread_type",
            name="uq_chat_threads_direct_pair",
        ),
    )
    op.create_index("ix_chat_threads_league_id", "chat_threads", ["league_id"])
    op.create_index(
        "uq_chat_threads_master_league",
        "chat_threads",
        ["league_id"],
        unique=True,
        postgresql_where=sa.text("thread_type = 'league'"),
        sqlite_where=sa.text("thread_type = 'league'"),
    )

    op.create_table(
        "chat_thread_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", "user_id", name="uq_chat_thread_participants_thread_user"),
    )
    op.create_index("ix_chat_thread_participants_user_id", "chat_thread_participants", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("league_id", sa.Integer(), nullable=False),
        sa.Column("sender_user_id", sa.Integer(), nullable=True),
        sa.Column("message_type", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("client_message_id", sa.String(length=100), nullable=True),
        sa.Column("event_key", sa.String(length=160), nullable=True),
        sa.Column("reply_to_message_id", sa.Integer(), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "message_type IN ('user', 'system', 'trade_finalized', 'trade_processed', 'waiver', 'draft', 'commissioner')",
            name="ck_chat_messages_type",
        ),
        sa.CheckConstraint("body IS NULL OR length(body) <= 2000", name="ck_chat_messages_body_length"),
        sa.ForeignKeyConstraint(
            ["thread_id", "league_id"],
            ["chat_threads.id", "chat_threads.league_id"],
            ondelete="CASCADE",
            name="fk_chat_messages_thread_league",
        ),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reply_to_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sender_user_id", "client_message_id", name="uq_chat_messages_sender_client_id"),
        sa.UniqueConstraint("event_key", name="uq_chat_messages_event_key"),
    )
    op.create_index("ix_chat_messages_thread_created", "chat_messages", ["thread_id", "created_at", "id"])
    op.create_index("ix_chat_messages_league_created", "chat_messages", ["league_id", "created_at", "id"])

    op.create_table(
        "chat_read_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_read_message_id", sa.Integer(), nullable=True),
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_read_message_id"], ["chat_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id", "user_id", name="uq_chat_read_states_thread_user"),
    )
    op.create_index("ix_chat_read_states_user_id", "chat_read_states", ["user_id"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO chat_threads (league_id, thread_type, title, is_archived)
            SELECT id, 'league', 'General', false
            FROM leagues
            """
        )
    )

    thread_rows = connection.execute(sa.text("SELECT id, league_id FROM chat_threads WHERE thread_type = 'league'"))
    thread_ids_by_league = {row.league_id: row.id for row in thread_rows}
    legacy_rows = connection.execute(
        sa.text(
            """
            SELECT id, league_id, user_id, message_type, body, created_at, updated_at
            FROM league_messages
            ORDER BY id
            """
        )
    ).mappings()
    legacy_messages = []
    for row in legacy_rows:
        legacy_messages.append(
            {
                "thread_id": thread_ids_by_league[row["league_id"]],
                "league_id": row["league_id"],
                "sender_user_id": row["user_id"],
                "message_type": _mapped_legacy_message_type(row["message_type"]),
                "body": row["body"],
                "metadata_json": {
                    "legacy_league_message_id": row["id"],
                    "legacy_message_type": row["message_type"],
                },
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    chat_messages = sa.table(
        "chat_messages",
        sa.column("thread_id", sa.Integer()),
        sa.column("league_id", sa.Integer()),
        sa.column("sender_user_id", sa.Integer()),
        sa.column("message_type", sa.String()),
        sa.column("body", sa.Text()),
        sa.column("metadata_json", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    if legacy_messages:
        op.bulk_insert(chat_messages, legacy_messages)

    imported_count = connection.execute(sa.text("SELECT count(*) FROM chat_messages")).scalar_one()
    legacy_count = connection.execute(sa.text("SELECT count(*) FROM league_messages")).scalar_one()
    if imported_count != legacy_count:
        raise RuntimeError(
            f"league chat migration imported {imported_count} messages but found {legacy_count} legacy messages"
        )

    _create_reply_thread_guards()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_chat_messages_reply_thread ON chat_messages")
        op.execute("DROP FUNCTION IF EXISTS enforce_chat_message_reply_thread()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_chat_messages_reply_thread_insert")
        op.execute("DROP TRIGGER IF EXISTS trg_chat_messages_reply_thread_update")

    op.drop_index("ix_chat_read_states_user_id", table_name="chat_read_states")
    op.drop_table("chat_read_states")
    op.drop_index("ix_chat_messages_league_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_created", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_thread_participants_user_id", table_name="chat_thread_participants")
    op.drop_table("chat_thread_participants")
    op.drop_index("uq_chat_threads_master_league", table_name="chat_threads")
    op.drop_index("ix_chat_threads_league_id", table_name="chat_threads")
    op.drop_table("chat_threads")
