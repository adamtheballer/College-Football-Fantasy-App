from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueMessage(TimestampMixin, Base):
    __tablename__ = "league_messages"
    __table_args__ = (
        Index("ix_league_messages_league_id_id", "league_id", "id"),
        Index("ix_league_messages_user_id", "user_id"),
        Index("ix_league_messages_parent_message_id", "parent_message_id"),
        Index("ix_league_messages_deleted_at", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(30), default="user")
    parent_message_id: Mapped[int | None] = mapped_column(ForeignKey("league_messages.id", ondelete="SET NULL"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeagueMessageRead(TimestampMixin, Base):
    __tablename__ = "league_message_reads"
    __table_args__ = (
        UniqueConstraint("user_id", "league_id", name="uq_league_message_reads_user_league"),
        Index("ix_league_message_reads_league_id", "league_id"),
        Index("ix_league_message_reads_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    last_read_message_id: Mapped[int | None] = mapped_column(ForeignKey("league_messages.id", ondelete="SET NULL"), nullable=True)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LeagueMessageReport(TimestampMixin, Base):
    __tablename__ = "league_message_reports"
    __table_args__ = (
        UniqueConstraint("message_id", "reporter_user_id", name="uq_league_message_reports_message_reporter"),
        Index("ix_league_message_reports_message_id", "message_id"),
        Index("ix_league_message_reports_reporter_user_id", "reporter_user_id"),
        Index("ix_league_message_reports_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("league_messages.id", ondelete="CASCADE"))
    reporter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="open")
