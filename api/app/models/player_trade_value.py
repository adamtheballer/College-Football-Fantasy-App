from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerTradeValue(TimestampMixin, Base):
    __tablename__ = "player_trade_values"
    __table_args__ = (
        UniqueConstraint("player_id", "season", "week", "policy_version", name="uq_player_trade_values_player_week_policy"),
        Index("ix_player_trade_values_player_season", "player_id", "season"),
        Index("ix_player_trade_values_season_week", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    tier: Mapped[str] = mapped_column(String(30), nullable=False)
    positional_value_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekly_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_version: Mapped[str] = mapped_column(String(80), nullable=False)
    explanation_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    factor_breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
