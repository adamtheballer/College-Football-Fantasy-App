from sqlalchemy import Boolean, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueSettings(TimestampMixin, Base):
    __tablename__ = "league_settings"
    __table_args__ = (
        Index("ix_league_settings_league_id", "league_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))

    scoring_json: Mapped[dict] = mapped_column(JSON, default={})
    roster_slots_json: Mapped[dict] = mapped_column(JSON, default={})
    playoff_teams: Mapped[int] = mapped_column(Integer, default=4)
    waiver_type: Mapped[str] = mapped_column(String(50), default="FAAB")
    waiver_mode: Mapped[str] = mapped_column(String(50), default="faab")
    waiver_period_hours: Mapped[int] = mapped_column(Integer, default=24)
    weekly_waiver_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    faab_budget: Mapped[int] = mapped_column(Integer, default=100)
    allow_zero_dollar_bids: Mapped[bool] = mapped_column(Boolean, default=True)
    trade_review_type: Mapped[str] = mapped_column(String(50), default="commissioner")

    superflex_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    kicker_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    defense_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
