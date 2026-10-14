"""Finalized, roster-independent weekly chart facts and durable coverage."""
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from collegefootballfantasy_api.app.models import Base, TimestampMixin

class PlayerChartWeek(TimestampMixin, Base):
    __tablename__ = "player_chart_weeks"
    __table_args__ = (UniqueConstraint("player_id", "season", "week", name="uq_player_chart_week"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer)
    stats_json: Mapped[dict] = mapped_column(JSON)
    standard_points: Mapped[float] = mapped_column(Float)
    scoring_rules_json: Mapped[dict] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    source_stat_id: Mapped[int | None] = mapped_column(ForeignKey("player_stats.id", ondelete="SET NULL"), nullable=True)
    finalized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    calculation_version: Mapped[str] = mapped_column(String(80))

class PlayerChartPublicationRun(TimestampMixin, Base):
    __tablename__ = "player_chart_publication_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    coverage_json: Mapped[dict] = mapped_column(JSON)


class PlayerChartForecast(TimestampMixin, Base):
    """Original evidenced pregame inputs, frozen independently of actuals."""
    __tablename__ = "player_chart_forecasts"
    __table_args__ = (UniqueConstraint("player_id","season","week",name="uq_player_chart_forecast"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id",ondelete="CASCADE"),index=True)
    season: Mapped[int] = mapped_column(Integer,index=True)
    week: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
