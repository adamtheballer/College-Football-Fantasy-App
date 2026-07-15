from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueSettings(TimestampMixin, Base):
    __tablename__ = "league_settings"
    __table_args__ = (
        Index("ix_league_settings_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))

    scoring_json: Mapped[dict] = mapped_column(JSON, default=dict)
    roster_slots_json: Mapped[dict] = mapped_column(JSON, default=dict)
    playoff_teams: Mapped[int] = mapped_column(Integer, default=4)
    waiver_type: Mapped[str] = mapped_column(String(50), default="FAAB")
    waiver_period_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    waiver_process_day: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    waiver_process_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_waiver_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    faab_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    allow_zero_dollar_bids: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    waiver_tiebreaker: Mapped[str] = mapped_column(String(50), nullable=False, default="priority")
    initial_waiver_priority_method: Mapped[str] = mapped_column(String(50), nullable=False, default="reverse_draft")
    post_drop_waiver_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    trade_review_type: Mapped[str] = mapped_column(String(50), default="commissioner")
    trade_deadline_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trade_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    superflex_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    kicker_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    defense_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def waiver_mode(self) -> str:
        return self.waiver_type
