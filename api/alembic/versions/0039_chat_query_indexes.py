"""add chat indexes for thread and unread query paths

Revision ID: 0039_chat_query_indexes
Revises: 0038_chat_security_audits
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0039_chat_query_indexes"
down_revision: str | Sequence[str] | None = "0038_chat_security_audits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_chat_threads_league_type", "chat_threads", ["league_id", "thread_type"])
    op.create_index(
        "ix_chat_thread_participants_user_thread",
        "chat_thread_participants",
        ["user_id", "thread_id"],
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id", "id"])
    op.create_index("ix_chat_messages_sender_user_id", "chat_messages", ["sender_user_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_messages_sender_user_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_index("ix_chat_thread_participants_user_thread", table_name="chat_thread_participants")
    op.drop_index("ix_chat_threads_league_type", table_name="chat_threads")
