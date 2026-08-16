from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderGamePoll(TimestampMixin, Base):
    """Durable per-game provider polling state.

    This row is the concurrency and rate-limit authority for a provider game.
    It deliberately has no fantasy-league foreign key: one provider response is
    shared by every roster and league that depends on the game.
    """

    __tablename__ = "provider_game_polls"
    __table_args__ = (
        UniqueConstraint("provider", "provider_game_id", name="uq_provider_game_polls_provider_game"),
        Index("ix_provider_game_polls_due", "provider", "next_poll_at", "lease_expires_at"),
        Index("ix_provider_game_polls_season_week", "provider", "season", "week"),
        Index("ix_provider_game_polls_status", "provider", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_game_id: Mapped[str] = mapped_column(String(128), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # The accepted fields are the sole canonical provider state.  Captured
    # snapshots may be stale or ambiguous and must never overwrite them.
    accepted_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_snapshot_classification: Mapped[str | None] = mapped_column(String(32), nullable=True)
    accepted_snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stale_snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ambiguous_snapshot_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_final_correction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProviderGameSnapshot(TimestampMixin, Base):
    """Immutable, deduplicated provider game snapshot for shadow/audit replay."""

    __tablename__ = "provider_game_snapshots"
    __table_args__ = (
        Index("ix_provider_game_snapshots_game_hash", "provider", "provider_game_id", "snapshot_hash"),
        Index("ix_provider_game_snapshots_game", "provider", "provider_game_id", "provider_as_of"),
        Index("ix_provider_game_snapshots_season_week", "provider", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_game_id: Mapped[str] = mapped_column(String(128), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # ``provider_as_of`` is only populated from a genuinely authoritative
    # provider field.  ``captured_at`` is our receipt time and is never used
    # to prove ordering.
    provider_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_etag: Mapped[str | None] = mapped_column(String(512), nullable=True)
    response_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    event_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_clock: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    classification: Mapped[str] = mapped_column(String(32), nullable=False, default="NEWER")
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalized_rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
