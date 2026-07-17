from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ChatThread(TimestampMixin, Base):
    __tablename__ = "chat_threads"
    __table_args__ = (
        CheckConstraint("thread_type IN ('league', 'direct')", name="ck_chat_threads_type"),
        CheckConstraint(
            "(thread_type = 'league' AND direct_user_low_id IS NULL AND direct_user_high_id IS NULL) OR "
            "(thread_type = 'direct' AND direct_user_low_id IS NOT NULL AND direct_user_high_id IS NOT NULL "
            "AND direct_user_low_id < direct_user_high_id)",
            name="ck_chat_threads_shape",
        ),
        UniqueConstraint("id", "league_id", name="uq_chat_threads_id_league"),
        UniqueConstraint(
            "league_id",
            "direct_user_low_id",
            "direct_user_high_id",
            "thread_type",
            name="uq_chat_threads_direct_pair",
        ),
        Index("ix_chat_threads_league_id", "league_id"),
        Index("ix_chat_threads_league_type", "league_id", "thread_type"),
        Index(
            "uq_chat_threads_master_league",
            "league_id",
            unique=True,
            postgresql_where=text("thread_type = 'league'"),
            sqlite_where=text("thread_type = 'league'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    thread_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    direct_user_low_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    direct_user_high_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)


class ChatThreadParticipant(TimestampMixin, Base):
    __tablename__ = "chat_thread_participants"
    __table_args__ = (
        UniqueConstraint("thread_id", "user_id", name="uq_chat_thread_participants_thread_user"),
        Index("ix_chat_thread_participants_user_id", "user_id"),
        Index("ix_chat_thread_participants_user_thread", "user_id", "thread_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint("message_type IN ('user', 'system', 'trade_finalized', 'trade_processed', 'waiver', 'draft', 'commissioner')", name="ck_chat_messages_type"),
        CheckConstraint("body IS NULL OR length(body) <= 2000", name="ck_chat_messages_body_length"),
        ForeignKeyConstraint(
            ["thread_id", "league_id"],
            ["chat_threads.id", "chat_threads.league_id"],
            ondelete="CASCADE",
            name="fk_chat_messages_thread_league",
        ),
        UniqueConstraint("sender_user_id", "client_message_id", name="uq_chat_messages_sender_client_id"),
        UniqueConstraint("event_key", name="uq_chat_messages_event_key"),
        Index("ix_chat_messages_thread_created", "thread_id", "created_at", "id"),
        Index("ix_chat_messages_thread_id", "thread_id", "id"),
        Index("ix_chat_messages_league_created", "league_id", "created_at", "id"),
        Index("ix_chat_messages_sender_user_id", "sender_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(nullable=False)
    league_id: Mapped[int] = mapped_column(nullable=False)
    sender_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    message_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    client_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatReadState(TimestampMixin, Base):
    __tablename__ = "chat_read_states"
    __table_args__ = (
        UniqueConstraint("thread_id", "user_id", name="uq_chat_read_states_thread_user"),
        Index("ix_chat_read_states_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    last_read_message_id: Mapped[int | None] = mapped_column(ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChatAuditEvent(TimestampMixin, Base):
    __tablename__ = "chat_audit_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_chat_audit_events_event_key"),
        Index("ix_chat_audit_events_league_created", "league_id", "created_at", "id"),
        Index("ix_chat_audit_events_action", "action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("chat_threads.id", ondelete="SET NULL"), nullable=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=text("'{}'"))
    event_key: Mapped[str | None] = mapped_column(String(180), nullable=True)
