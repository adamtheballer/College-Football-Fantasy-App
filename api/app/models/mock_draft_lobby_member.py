from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class MockDraftLobbyMember(TimestampMixin, Base):
    __tablename__ = "mock_draft_lobby_members"
    __table_args__ = (
        UniqueConstraint("session_id", "seat_id", name="uq_mock_draft_lobby_members_session_seat"),
        UniqueConstraint("session_id", "user_id", name="uq_mock_draft_lobby_members_session_user"),
        Index("ix_mock_draft_lobby_members_session_id", "session_id"),
        Index("ix_mock_draft_lobby_members_seat_id", "seat_id"),
        Index("ix_mock_draft_lobby_members_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    seat_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_seats.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
