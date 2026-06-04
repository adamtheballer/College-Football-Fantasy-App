from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class LeagueWeekState(TimestampMixin, Base):
    __tablename__ = "league_week_states"
    __table_args__ = (
        UniqueConstraint("league_id", "season", "week", name="uq_league_week_states_league_season_week"),
        Index("ix_league_week_states_league_id", "league_id"),
        Index("ix_league_week_states_season_week", "season", "week"),
        Index("ix_league_week_states_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="open")
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    corrected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
