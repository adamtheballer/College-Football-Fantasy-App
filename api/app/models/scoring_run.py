from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ScoringRun(TimestampMixin, Base):
    __tablename__ = "scoring_runs"
    __table_args__ = (
        Index("ix_scoring_runs_league_week", "league_id", "season", "week"),
        Index("ix_scoring_runs_status", "status"),
        Index("ix_scoring_runs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    source_mode: Mapped[str] = mapped_column(String(40), default="actual_then_projection")
    status: Mapped[str] = mapped_column(String(20), default="running")
    finalize_matchups: Mapped[bool] = mapped_column(default=False)
    finalized_week_state: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
