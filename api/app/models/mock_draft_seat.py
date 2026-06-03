from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MockDraftSeat(TimestampMixin, Base):
    __tablename__ = "mock_draft_seats"
    __table_args__ = (
        UniqueConstraint("session_id", "seat_number", name="uq_mock_draft_seats_session_seat_number"),
        UniqueConstraint("session_id", "owner_user_id", name="uq_mock_draft_seats_session_owner"),
        Index("ix_mock_draft_seats_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    seat_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_cpu: Mapped[bool] = mapped_column(Boolean, default=False)
