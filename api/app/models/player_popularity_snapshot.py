"""Published, daily league-popularity aggregates.

These rows are deliberately snapshots instead of mutable counters.  Ownership,
lineup use, and pickup history are reconstructed from the product's durable
league records by the lifecycle worker, then published atomically for readers.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerPopularitySnapshot(TimestampMixin, Base):
    __tablename__ = "player_popularity_snapshots"
    __table_args__ = (
        UniqueConstraint("season", "snapshot_date", name="uq_player_popularity_snapshot_date"),
        Index("ix_player_popularity_snapshots_published", "season", "status", "published_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    # UTC calendar date for the scheduled 06:00 reconciliation.
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    coverage_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PlayerPopularityMetric(Base):
    __tablename__ = "player_popularity_metrics"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "player_id", name="uq_player_popularity_metric_snapshot_player"),
        Index("ix_player_popularity_metrics_player", "player_id", "snapshot_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("player_popularity_snapshots.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    eligible_league_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rostered_league_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_league_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # A zero starter count is meaningful only after at least one relevant
    # kickoff snapshot exists for the player in the eligible cohort.
    start_sample_league_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PlayerHotPickupMetric(Base):
    __tablename__ = "player_hot_pickup_metrics"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "window_hours", "player_id", name="uq_player_hot_pickup_snapshot_window_player"),
        Index("ix_player_hot_pickup_metrics_window", "snapshot_id", "window_hours", "pickup_league_count"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("player_popularity_snapshots.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    pickup_league_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
