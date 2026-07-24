from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueSettings(TimestampMixin, Base):
    __tablename__ = "league_settings"
    __table_args__ = (
        Index("ix_league_settings_league_id", "league_id"),
        CheckConstraint("waiver_type IN ('faab', 'priority')", name="ck_league_settings_waiver_type"),
        CheckConstraint("faab_starting_budget >= 0", name="ck_league_settings_faab_starting_budget"),
        CheckConstraint("waiver_processing_weekday BETWEEN 0 AND 6", name="ck_league_settings_waiver_processing_weekday"),
        CheckConstraint("waiver_processing_hour BETWEEN 0 AND 23", name="ck_league_settings_waiver_processing_hour"),
        CheckConstraint("post_drop_waiver_hours >= 0", name="ck_league_settings_post_drop_waiver_hours"),
        CheckConstraint("free_agent_mode IN ('after_waivers_clear')", name="ck_league_settings_free_agent_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))

    scoring_json: Mapped[dict] = mapped_column(JSON, default=dict)
    roster_slots_json: Mapped[dict] = mapped_column(JSON, default=dict)
    playoff_teams: Mapped[int] = mapped_column(Integer, default=4)
    waiver_type: Mapped[str] = mapped_column(String(50), nullable=False, default="faab")
    waiver_period_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    # Python weekday: Monday=0, Tuesday=1. Tuesday begins each CFB fantasy week.
    waiver_processing_weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    waiver_processing_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    waiver_timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")
    next_waiver_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    faab_starting_budget: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    allow_zero_faab_bids: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    waiver_tiebreaker: Mapped[str] = mapped_column(String(50), nullable=False, default="priority")
    initial_waiver_priority_method: Mapped[str] = mapped_column(String(50), nullable=False, default="reverse_draft")
    reveal_all_waiver_bids: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    post_drop_waiver_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    waiver_initialized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waivers_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    free_agent_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="after_waivers_clear")
    trade_review_type: Mapped[str] = mapped_column(String(50), default="commissioner")
    trade_deadline_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trade_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    superflex_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    kicker_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    defense_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    @property
    def waiver_mode(self) -> str:
        return self.waiver_type

    @property
    def waiver_process_day(self) -> int:
        return self.waiver_processing_weekday

    @property
    def waiver_process_hour(self) -> int:
        return self.waiver_processing_hour

    @property
    def faab_budget(self) -> int:
        return self.faab_starting_budget

    @property
    def allow_zero_dollar_bids(self) -> bool:
        return self.allow_zero_faab_bids
