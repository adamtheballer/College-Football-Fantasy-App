"""Durable, source-of-truth career history and league rivalry records."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class UserCareerEvent(TimestampMixin, Base):
    """An immutable, idempotent record of a meaningful fantasy-career event."""

    __tablename__ = "user_career_events"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_user_career_events_source_key"),
        Index("ix_user_career_events_user_occurred", "user_id", "occurred_at"),
        Index("ix_user_career_events_league", "league_id", "season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_key: Mapped[str] = mapped_column(String(240), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    league_id: Mapped[int | None] = mapped_column(ForeignKey("leagues.id", ondelete="SET NULL"), nullable=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    matchup_id: Mapped[int | None] = mapped_column(ForeignKey("matchups.id", ondelete="SET NULL"), nullable=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trade_offers.id", ondelete="SET NULL"), nullable=True)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("drafts.id", ondelete="SET NULL"), nullable=True)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeagueRivalry(TimestampMixin, Base):
    """One user-owned, league-season rivalry. Changes are audited in career events."""

    __tablename__ = "league_rivalries"
    __table_args__ = (
        UniqueConstraint("league_id", "season", "team_id", name="uq_league_rivalries_team_season"),
        CheckConstraint("team_id <> rival_team_id", name="ck_league_rivalries_distinct_teams"),
        Index("ix_league_rivalries_league_season", "league_id", "season"),
        Index("ix_league_rivalries_rival_team", "rival_team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    rival_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    selected_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rivalry_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
