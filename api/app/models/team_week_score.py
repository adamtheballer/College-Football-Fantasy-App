from sqlalchemy import Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TeamWeekScore(TimestampMixin, Base):
    __tablename__ = "team_week_scores"
    __table_args__ = (
        UniqueConstraint("team_id", "season", "week", name="uq_team_week_scores_team_season_week"),
        Index("ix_team_week_scores_team_id", "team_id"),
        Index("ix_team_week_scores_league_week", "league_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    points_total: Mapped[float] = mapped_column(Float, default=0.0)
    points_starters: Mapped[float] = mapped_column(Float, default=0.0)
    points_bench: Mapped[float] = mapped_column(Float, default=0.0)
