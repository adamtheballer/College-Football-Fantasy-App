from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerWeekScore(TimestampMixin, Base):
    __tablename__ = "player_week_scores"
    __table_args__ = (
        UniqueConstraint("league_id", "player_id", "season", "week", name="uq_player_week_scores_league_player_week"),
        Index("ix_player_week_scores_league_week", "league_id", "season", "week"),
        Index("ix_player_week_scores_player_id", "player_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    fantasy_points: Mapped[float] = mapped_column(Float, default=0.0)
    breakdown_json: Mapped[dict] = mapped_column(JSON, default={})
    source_stat_id: Mapped[int | None] = mapped_column(ForeignKey("player_stats.id", ondelete="SET NULL"), nullable=True)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
