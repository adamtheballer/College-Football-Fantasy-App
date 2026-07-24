from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TeamSchedule(TimestampMixin, Base):
    """One canonical schedule row for a team's season and week.

    Schedule rows belong to teams, not players. Player game logs overlay verified
    PlayerGameStat values on these durable team/week rows.
    """

    __tablename__ = "team_schedules"
    __table_args__ = (
        UniqueConstraint("team_name", "season", "week", name="uq_team_schedules_team_season_week"),
        CheckConstraint("location IN ('home', 'away', 'neutral', 'bye')", name="ck_team_schedules_location"),
        Index("ix_team_schedules_team_season", "team_name", "season"),
        Index("ix_team_schedules_game_id", "game_id"),
        Index("ix_team_schedules_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"), nullable=True)
    opponent_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location: Mapped[str] = mapped_column(String(16), nullable=False)
    is_bye: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    game_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    neutral_site: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conference_game: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    tv_network: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
