from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MockDraftTimerState(TimestampMixin, Base):
    __tablename__ = "mock_draft_timer_states"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_mock_draft_timer_states_session_id"),
        Index("ix_mock_draft_timer_states_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    timer_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_total_seconds: Mapped[int] = mapped_column(Integer, default=0)
    last_tick_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_picking_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_picking_pick_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, default=1)
