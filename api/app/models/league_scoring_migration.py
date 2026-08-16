from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class LeagueScoringMigration(TimestampMixin, Base):
    """Immutable, idempotent evidence for a deliberate league scoring correction."""

    __tablename__ = "league_scoring_migrations"
    __table_args__ = (
        UniqueConstraint("league_id", "migration_key", name="uq_league_scoring_migrations_league_key"),
        Index("ix_league_scoring_migrations_league_id", "league_id"),
        Index("ix_league_scoring_migrations_migration_key", "migration_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    league_settings_id: Mapped[int] = mapped_column(ForeignKey("league_settings.id", ondelete="RESTRICT"), nullable=False)
    migration_key: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    before_scoring_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    before_scoring_snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_scoring_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
