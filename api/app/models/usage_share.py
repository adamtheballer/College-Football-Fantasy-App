from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class UsageShare(TimestampMixin, Base):
    __tablename__ = "usage_shares"
    __table_args__ = (
        Index("ix_usage_shares_player_id", "player_id"),
        Index("ix_usage_shares_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    projection_version: Mapped[str] = mapped_column(String(20), default="FINAL")

    rush_share: Mapped[float] = mapped_column(Float, default=0.0)
    target_share: Mapped[float] = mapped_column(Float, default=0.0)
    pass_share: Mapped[float] = mapped_column(Float, default=0.0)
    kicker_share: Mapped[float] = mapped_column(Float, default=0.0)
    red_zone_share: Mapped[float] = mapped_column(Float, default=0.0)
    inside_five_share: Mapped[float] = mapped_column(Float, default=0.0)
    snap_share: Mapped[float] = mapped_column(Float, default=0.0)
    route_share: Mapped[float] = mapped_column(Float, default=0.0)
    prior_rush_share: Mapped[float] = mapped_column(Float, default=0.0)
    prior_target_share: Mapped[float] = mapped_column(Float, default=0.0)
    prior_kicker_share: Mapped[float] = mapped_column(Float, default=0.0)
    projected_rush_share: Mapped[float] = mapped_column(Float, default=0.0)
    projected_target_share: Mapped[float] = mapped_column(Float, default=0.0)
    projected_kicker_share: Mapped[float] = mapped_column(Float, default=0.0)
    pre_normalization_role_score: Mapped[float] = mapped_column(Float, default=0.0)
    raw_usage_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    usage_confidence: Mapped[float] = mapped_column(Float, default=0.5)
    applied_usage_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    fallback_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adjustment_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
