from sqlalchemy import Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class Matchup(TimestampMixin, Base):
    __tablename__ = "matchups"
    __table_args__ = (
        UniqueConstraint("league_id", "season", "week", "home_team_id", "away_team_id", name="uq_matchup_unique"),
        Index("ix_matchups_league_week", "league_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    home_score: Mapped[float] = mapped_column(Float, default=0.0)
    away_score: Mapped[float] = mapped_column(Float, default=0.0)
