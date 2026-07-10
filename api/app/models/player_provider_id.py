from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerProviderId(TimestampMixin, Base):
    __tablename__ = "player_provider_ids"
    __table_args__ = (
        UniqueConstraint("provider", "provider_player_id", name="uq_player_provider_ids_provider_player"),
        UniqueConstraint("player_id", "provider", name="uq_player_provider_ids_player_provider"),
        Index("ix_player_provider_ids_player_id", "player_id"),
        Index("ix_player_provider_ids_provider_team", "provider", "provider_team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_player_id: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_team_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    match_confidence: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    player = relationship("Player", back_populates="provider_ids")
