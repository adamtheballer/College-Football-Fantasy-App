from sqlalchemy import Float, ForeignKey, Index, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base, TimestampMixin


class TeamWeeklyScore(TimestampMixin, Base):
    __tablename__ = "team_weekly_scores"
    __table_args__ = (
        UniqueConstraint("league_id", "team_id", "season", "week", name="uq_team_weekly_scores_team_week"),
        Index("ix_team_weekly_scores_league_week", "league_id", "season", "week"),
        Index("ix_team_weekly_scores_team_week", "team_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    lineup_id: Mapped[int | None] = mapped_column(ForeignKey("lineups.id", ondelete="SET NULL"), nullable=True)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    starter_points: Mapped[float] = mapped_column(Float, default=0.0)
    bench_points: Mapped[float] = mapped_column(Float, default=0.0)
    total_points: Mapped[float] = mapped_column(Float, default=0.0)
    breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
