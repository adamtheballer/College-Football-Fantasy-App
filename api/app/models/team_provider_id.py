from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class TeamProviderId(TimestampMixin, Base):
    __tablename__ = "team_provider_ids"
    __table_args__ = (
        UniqueConstraint("provider", "provider_team_id", name="uq_team_provider_ids_provider_team"),
        UniqueConstraint("canonical_school", "provider", name="uq_team_provider_ids_school_provider"),
        Index("ix_team_provider_ids_school", "canonical_school"),
        Index("ix_team_provider_ids_provider_team", "provider", "provider_team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_school: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_team_id: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_abbreviation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    match_confidence: Mapped[int] = mapped_column(Integer, default=100)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
