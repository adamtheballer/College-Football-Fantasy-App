from sqlalchemy import Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TeamStatsSnapshot(TimestampMixin, Base):
    __tablename__ = "team_stats_snapshots"
    __table_args__ = (
        UniqueConstraint("team_name", "season", "week", "scope", name="uq_team_stats_snapshot_team_season_week_scope"),
        Index("ix_team_stats_snapshots_team_name", "team_name"),
        Index("ix_team_stats_snapshots_conference", "conference"),
        Index("ix_team_stats_snapshots_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_name: Mapped[str] = mapped_column(String(200))
    conference: Mapped[str] = mapped_column(String(10))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer, default=0)
    scope: Mapped[str] = mapped_column(String(30), default="season")
    offense_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    defense_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    advanced_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(50), default="cfbd")
