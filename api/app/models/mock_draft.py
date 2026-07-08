from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, JSON, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class MockDraft(TimestampMixin, Base):
    __tablename__ = "mock_drafts"
    __table_args__ = (
        Index("ix_mock_drafts_owner_user_id", "owner_user_id"),
        Index("ix_mock_drafts_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120), default="Single-Player Mock Draft")
    status: Mapped[str] = mapped_column(String(30), default="active")
    league_size: Mapped[int] = mapped_column(Integer, default=12)
    rounds: Mapped[int] = mapped_column(Integer, default=13)
    current_pick: Mapped[int] = mapped_column(Integer, default=1)
    user_team_index: Mapped[int] = mapped_column(Integer, default=1)
    cpu_strategy: Mapped[str] = mapped_column(String(40), default="rank_position_need")
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    picks = relationship("MockDraftPick", back_populates="mock_draft", cascade="all, delete-orphan")
    queue = relationship("MockDraftQueueEntry", cascade="all, delete-orphan")
