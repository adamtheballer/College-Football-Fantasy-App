from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MockDraftSession(TimestampMixin, Base):
    __tablename__ = "mock_draft_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    commissioner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invite_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="Mock Draft")
    status: Mapped[str] = mapped_column(String(30), default="filling", index=True)
    manager_count: Mapped[int] = mapped_column(Integer, default=12)
    draft_type: Mapped[str] = mapped_column(String(30), default="snake")
    pick_timer_seconds: Mapped[int] = mapped_column(Integer, default=90)
    roster_slots_json: Mapped[dict] = mapped_column(JSON, default=dict)
    scoring_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_datetime_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
