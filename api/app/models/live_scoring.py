"""Append-only persistence records for production-grade live scoring.

These tables deliberately sit alongside legacy score read models.  The worker
may publish from a verified snapshot only in an explicitly enabled runtime;
beta remains disabled/shadow-only.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class ProviderGameIdentity(TimestampMixin, Base):
    __tablename__ = "provider_game_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_game_id", name="uq_provider_game_identity"),
        UniqueConstraint("game_id", "provider", name="uq_game_provider_identity"),
        Index("ix_provider_game_identities_status", "verification_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_game_id: Mapped[str] = mapped_column(String(128), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unverified")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ProviderRawEvent(Base):
    __tablename__ = "provider_raw_events"
    __table_args__ = (
        UniqueConstraint("provider", "feed", "provider_event_id", name="uq_provider_raw_event"),
        UniqueConstraint("provider", "endpoint_type", "provider_game_id", "payload_sha256", name="uq_provider_raw_payload"),
        Index("ix_provider_raw_events_player_game", "provider", "provider_player_id", "provider_game_id"),
        Index("ix_provider_raw_events_received_at", "received_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    feed: Mapped[str] = mapped_column(String(100), nullable=False)
    endpoint_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    request_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    provider_revision: Mapped[str | None] = mapped_column(String(160), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="player_stat_revision")
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_player_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_team_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_game_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="received")
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlayerGameStatRevision(Base):
    __tablename__ = "player_game_stat_revisions"
    __table_args__ = (
        UniqueConstraint("player_id", "game_id", "revision_number", name="uq_player_game_stat_revision"),
        UniqueConstraint("provider", "provider_player_id", "provider_game_id", "source_hash", name="uq_provider_stat_revision_hash"),
        Index("ix_player_game_stat_revisions_player_game", "player_id", "game_id"),
        Index("ix_player_game_stat_revisions_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("provider_raw_events.id", ondelete="RESTRICT"), nullable=False)
    supersedes_revision_id: Mapped[int | None] = mapped_column(ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_player_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_game_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_revision: Mapped[str | None] = mapped_column(String(160), nullable=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(30), nullable=False)
    completeness: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="accepted")
    stats_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    missing_keys_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScoringCalculationSnapshot(Base):
    __tablename__ = "scoring_calculation_snapshots"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_scoring_snapshot_idempotency"),
        Index("ix_scoring_snapshots_league_week", "league_id", "season", "week"),
        Index("ix_scoring_snapshots_revision", "stat_revision_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    stat_revision_id: Mapped[int] = mapped_column(ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=False)
    league_scoring_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("league_scoring_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("provider_raw_events.id", ondelete="RESTRICT"), nullable=False)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    scorer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scoring_policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    publish_state: Mapped[str] = mapped_column(String(30), nullable=False, default="shadow")
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ShadowScoringReadModel(Base):
    """Immutable, shadow-only projection of one league scoring window.

    This table is deliberately separate from the mutable public score,
    matchup, and standing read models.  A source hash identifies the exact
    lineup locks and scoring snapshots used to derive the payload, so an
    operator can compare a correction or replay without overwriting evidence.
    """

    __tablename__ = "shadow_scoring_read_models"
    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "season",
            "week",
            "source_sha256",
            name="uq_shadow_scoring_read_model_source",
        ),
        Index("ix_shadow_scoring_read_models_league_week", "league_id", "season", "week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeagueScoringSnapshot(Base):
    """Immutable league-season scoring policy used for every calculated score."""

    __tablename__ = "league_scoring_snapshots"
    __table_args__ = (
        UniqueConstraint("league_id", "season", "rules_sha256", "calculation_version", name="uq_league_scoring_snapshot"),
        Index("ix_league_scoring_snapshots_league_season", "league_id", "season"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    rules_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    rules_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScoringWorkItem(TimestampMixin, Base):
    __tablename__ = "scoring_work_items"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_scoring_work_item_idempotency"),
        Index("ix_scoring_work_items_ready", "status", "next_attempt_at"),
        Index("ix_scoring_work_items_lease", "lease_expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScoringDeadLetter(Base):
    __tablename__ = "scoring_dead_letters"
    __table_args__ = (UniqueConstraint("work_item_id", name="uq_scoring_dead_letter_work_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_item_id: Mapped[int] = mapped_column(ForeignKey("scoring_work_items.id", ondelete="CASCADE"), nullable=False)
    failure_category: Mapped[str] = mapped_column(String(80), nullable=False)
    failure_message: Mapped[str] = mapped_column(Text, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScoringCorrectionLedger(Base):
    __tablename__ = "scoring_correction_ledger"
    __table_args__ = (Index("ix_scoring_correction_ledger_player_game", "player_id", "game_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), nullable=False)
    prior_revision_id: Mapped[int] = mapped_column(ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=False)
    corrected_revision_id: Mapped[int] = mapped_column(ForeignKey("player_game_stat_revisions.id", ondelete="RESTRICT"), nullable=False)
    raw_event_id: Mapped[int] = mapped_column(ForeignKey("provider_raw_events.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    impact_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
