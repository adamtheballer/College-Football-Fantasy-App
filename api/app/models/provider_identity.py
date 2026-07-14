from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class PlayerProviderId(TimestampMixin, Base):
    __tablename__ = "player_provider_ids"
    __table_args__ = (
        UniqueConstraint("provider", "provider_player_id", name="uq_player_provider_ids_provider_player"),
        UniqueConstraint("player_id", "provider", name="uq_player_provider_ids_player_provider"),
        Index("ix_player_provider_ids_player_id", "player_id"),
        Index("ix_player_provider_ids_provider", "provider"),
        Index("ix_player_provider_ids_verification_status", "verification_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_player_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_team_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unverified")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    player = relationship("Player")
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])


class TeamProviderId(TimestampMixin, Base):
    __tablename__ = "team_provider_ids"
    __table_args__ = (
        UniqueConstraint("provider", "provider_team_id", name="uq_team_provider_ids_provider_team"),
        UniqueConstraint("team_id", "provider", name="uq_team_provider_ids_team_provider"),
        Index("ix_team_provider_ids_team_id", "team_id"),
        Index("ix_team_provider_ids_provider", "provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("college_teams.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_team_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    team = relationship("CollegeTeam", back_populates="provider_ids")


class UnmatchedProviderRow(TimestampMixin, Base):
    __tablename__ = "unmatched_provider_rows"
    __table_args__ = (
        UniqueConstraint("provider", "feed", "dedupe_hash", name="uq_unmatched_provider_rows_provider_feed_hash"),
        Index("ix_unmatched_provider_rows_status", "status"),
        Index("ix_unmatched_provider_rows_provider_feed", "provider", "feed"),
        Index("ix_unmatched_provider_rows_provider_player_id", "provider_player_id"),
        Index("ix_unmatched_provider_rows_provider_team_id", "provider_team_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    feed: Mapped[str] = mapped_column(String(100), nullable=False)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_player_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    player_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dedupe_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mapped_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    mapped_player = relationship("Player", foreign_keys=[mapped_player_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])


class ProviderIdentityAudit(TimestampMixin, Base):
    __tablename__ = "provider_identity_audits"
    __table_args__ = (
        Index("ix_provider_identity_audits_entity", "entity_type", "entity_id"),
        Index("ix_provider_identity_audits_provider", "provider"),
        Index("ix_provider_identity_audits_actor_user_id", "actor_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_player_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    unmatched_row_id: Mapped[int | None] = mapped_column(
        ForeignKey("unmatched_provider_rows.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    actor = relationship("User", foreign_keys=[actor_user_id])
    unmatched_row = relationship("UnmatchedProviderRow")
