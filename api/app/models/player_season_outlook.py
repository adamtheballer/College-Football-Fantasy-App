from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerSeasonOutlook(TimestampMixin, Base):
    """Auditable, deterministic preseason outlook rendered by the player card."""

    __tablename__ = "player_season_outlooks"
    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "season_year",
            "outlook_type",
            "generator_version",
            name="uq_player_season_outlooks_identity",
        ),
        Index("ix_player_season_outlooks_player_season", "player_id", "season_year"),
        Index("ix_player_season_outlooks_season_status", "season_year", "outlook_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    outlook_type: Mapped[str] = mapped_column(String(30), nullable=False, default="PRESEASON")
    generator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    facts_version: Mapped[str] = mapped_column(String(80), nullable=False)
    facts_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    outlook_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    outlook_status: Mapped[str] = mapped_column(String(40), nullable=False)
    historical_source_batch_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    projection_source_batch_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    identity_source_batch_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="AUTO_APPROVED")
