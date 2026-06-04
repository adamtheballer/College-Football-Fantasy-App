from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class MockDraftParticipant(TimestampMixin, Base):
    __tablename__ = "mock_draft_participants"
    __table_args__ = (
        UniqueConstraint("mock_draft_id", "user_id", name="uq_mock_draft_participants_draft_user"),
        UniqueConstraint("mock_draft_id", "seat_number", name="uq_mock_draft_participants_draft_seat"),
        UniqueConstraint("mock_draft_id", "draft_position", name="uq_mock_draft_participants_draft_position"),
        Index("ix_mock_draft_participants_mock_draft_id", "mock_draft_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    mock_draft_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200))
    team_name: Mapped[str] = mapped_column(String(200))
    participant_type: Mapped[str] = mapped_column(String(30), default="human")
    seat_number: Mapped[int] = mapped_column(Integer)
    draft_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connection_status: Mapped[str] = mapped_column(String(30), default="connected")
    auto_pick_count: Mapped[int] = mapped_column(Integer, default=0)
