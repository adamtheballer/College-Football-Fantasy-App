from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Draft(TimestampMixin, Base):
    __tablename__ = "drafts"
    __table_args__ = (
        Index("ix_drafts_league_id", "league_id"),
        Index("ix_drafts_datetime", "draft_datetime_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    draft_datetime_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    draft_type: Mapped[str] = mapped_column(String(30), default="snake")
    pick_timer_seconds: Mapped[int] = mapped_column(Integer, default=90)
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
