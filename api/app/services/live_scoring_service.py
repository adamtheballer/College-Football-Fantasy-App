"""Append-only, idempotent live-scoring pipeline services.

Nothing in this module fetches a provider or mutates public score read models.
The caller records a provider event, verifies exact provider identities, stores
an immutable stat revision, and can then calculate a shadow/public snapshot.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.live_scoring_contract import (
    COMPLETE,
    VALID_GAME_LIFECYCLES,
    IncompleteStatRevisionError,
    LiveScoringContractError,
    normalize_live_stat_revision,
    validate_lifecycle_transition,
)
from collegefootballfantasy_api.app.domain.scoring_engine import CALCULATION_VERSION, calculate_player_fantasy_points
from collegefootballfantasy_api.app.models.live_scoring import (
    LeagueScoringSnapshot,
    PlayerGameStatRevision,
    ProviderGameIdentity,
    ProviderRawEvent,
    ScoringCalculationSnapshot,
    ScoringCorrectionLedger,
    ScoringDeadLetter,
    ScoringWorkItem,
)
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId


class IdentityResolutionError(LiveScoringContractError):
    """No reviewed exact identity exists for a provider record."""


class ImmutableProviderEventError(LiveScoringContractError):
    """An existing provider event id was reused with different contents."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProviderEventInput:
    provider: str
    feed: str
    provider_event_id: str
    payload: dict[str, Any]
    event_type: str = "player_stat_revision"
    endpoint_type: str | None = None
    request_key: str | None = None
    provider_revision: str | None = None
    http_status: int | None = None
    schema_version: str | None = None
    season: int | None = None
    week: int | None = None
    provider_player_id: str | None = None
    provider_team_id: str | None = None
    provider_game_id: str | None = None
    occurred_at: datetime | None = None


def record_provider_event(db: Session, event: ProviderEventInput) -> ProviderRawEvent:
    """Persist a raw provider event exactly once without overwriting history."""
    payload_hash = sha256(event.payload)
    endpoint_type = event.endpoint_type or event.feed
    existing = (
        db.query(ProviderRawEvent)
        .filter(
            ProviderRawEvent.provider == event.provider,
            ProviderRawEvent.feed == event.feed,
            ProviderRawEvent.provider_event_id == event.provider_event_id,
        )
        .one_or_none()
    )
    if existing:
        if existing.payload_sha256 != payload_hash:
            raise ImmutableProviderEventError(
                "provider event id was reused with a different payload; corrective events require a new provider event id"
            )
        return existing
    if event.provider_game_id:
        duplicate_payload = (
            db.query(ProviderRawEvent)
            .filter(
                ProviderRawEvent.provider == event.provider,
                ProviderRawEvent.endpoint_type == endpoint_type,
                ProviderRawEvent.provider_game_id == event.provider_game_id,
                ProviderRawEvent.payload_sha256 == payload_hash,
            )
            .one_or_none()
        )
        if duplicate_payload:
            return duplicate_payload
    row = ProviderRawEvent(
        provider=event.provider,
        feed=event.feed,
        endpoint_type=endpoint_type,
        provider_event_id=event.provider_event_id,
        request_key=event.request_key,
        provider_revision=event.provider_revision,
        http_status=event.http_status,
        schema_version=event.schema_version,
        event_type=event.event_type,
        season=event.season,
        week=event.week,
        provider_player_id=event.provider_player_id,
        provider_team_id=event.provider_team_id,
        provider_game_id=event.provider_game_id,
        payload_json=event.payload,
        payload_sha256=payload_hash,
        occurred_at=event.occurred_at,
        received_at=utcnow(),
        processing_status="received",
    )
    db.add(row)
    db.flush()
    return row


def resolve_exact_player_id(db: Session, *, provider: str, provider_player_id: str) -> int:
    identity = (
        db.query(PlayerProviderId)
        .filter(
            PlayerProviderId.provider == provider,
            PlayerProviderId.provider_player_id == provider_player_id,
        )
        .one_or_none()
    )
    if identity is None or identity.verification_status != "verified":
        raise IdentityResolutionError("provider player identity is missing or not verified")
    return identity.player_id


def resolve_exact_game_id(db: Session, *, provider: str, provider_game_id: str) -> int:
    identity = (
        db.query(ProviderGameIdentity)
        .filter(
            ProviderGameIdentity.provider == provider,
            ProviderGameIdentity.provider_game_id == provider_game_id,
        )
        .one_or_none()
    )
    if identity is None or identity.verification_status != "verified":
        raise IdentityResolutionError("provider game identity is missing or not verified")
    return identity.game_id


def _latest_revision(db: Session, *, player_id: int, game_id: int) -> PlayerGameStatRevision | None:
    return (
        db.query(PlayerGameStatRevision)
        .filter(PlayerGameStatRevision.player_id == player_id, PlayerGameStatRevision.game_id == game_id)
        .order_by(PlayerGameStatRevision.revision_number.desc())
        .first()
    )


def record_stat_revision(
    db: Session,
    *,
    raw_event: ProviderRawEvent,
    position: str | None,
    season: int,
    week: int,
    lifecycle_state: str,
    completeness: str,
    stats: dict[str, Any],
    correction_reason: str | None = None,
) -> PlayerGameStatRevision:
    """Record one immutable, exact-identity provider stat revision.

    Incomplete payloads are saved as blocked evidence, but cannot be used for
    a score.  This preserves forensic input without converting omitted values
    to zero.
    """
    if lifecycle_state not in VALID_GAME_LIFECYCLES:
        raise LiveScoringContractError("invalid game lifecycle state")
    if not raw_event.provider_player_id or not raw_event.provider_game_id:
        raise IdentityResolutionError("stat revisions require exact provider player and game ids")
    player_id = resolve_exact_player_id(
        db, provider=raw_event.provider, provider_player_id=raw_event.provider_player_id
    )
    game_id = resolve_exact_game_id(db, provider=raw_event.provider, provider_game_id=raw_event.provider_game_id)
    normalized = normalize_live_stat_revision(stats, position, completeness=completeness)
    source_hash = sha256(
        {
            "event": raw_event.payload_sha256,
            "season": season,
            "week": week,
            "lifecycle": lifecycle_state,
            "completeness": completeness,
            "stats": normalized.stats,
        }
    )
    existing = (
        db.query(PlayerGameStatRevision)
        .filter(
            PlayerGameStatRevision.provider == raw_event.provider,
            PlayerGameStatRevision.provider_player_id == raw_event.provider_player_id,
            PlayerGameStatRevision.provider_game_id == raw_event.provider_game_id,
            PlayerGameStatRevision.source_hash == source_hash,
        )
        .one_or_none()
    )
    if existing:
        return existing
    prior = _latest_revision(db, player_id=player_id, game_id=game_id)
    validate_lifecycle_transition(prior.lifecycle_state if prior else None, lifecycle_state)
    row = PlayerGameStatRevision(
        raw_event_id=raw_event.id,
        supersedes_revision_id=prior.id if prior else None,
        player_id=player_id,
        game_id=game_id,
        provider=raw_event.provider,
        provider_player_id=raw_event.provider_player_id,
        provider_game_id=raw_event.provider_game_id,
        provider_revision=raw_event.provider_revision,
        season=season,
        week=week,
        revision_number=(prior.revision_number + 1) if prior else 1,
        lifecycle_state=lifecycle_state,
        completeness=normalized.completeness,
        status="accepted" if normalized.scoreable else "blocked_incomplete",
        stats_json=normalized.stats,
        missing_keys_json=list(normalized.missing_keys),
        source_hash=source_hash,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    raw_event.processing_status = "revision_recorded"
    raw_event.processed_at = utcnow()
    if prior:
        db.add(
            ScoringCorrectionLedger(
                player_id=player_id,
                game_id=game_id,
                prior_revision_id=prior.id,
                corrected_revision_id=row.id,
                raw_event_id=raw_event.id,
                reason=correction_reason or "provider_stat_revision",
                impact_json={"previous_revision": prior.revision_number, "new_revision": row.revision_number},
                created_at=utcnow(),
            )
        )
        db.flush()
    return row


def _policy_hash(scoring_rules: dict | None) -> str:
    return sha256(scoring_rules or {})


def get_or_create_league_scoring_snapshot(
    db: Session,
    *,
    league_id: int,
    season: int,
    scoring_rules: dict | None,
) -> LeagueScoringSnapshot:
    """Lock the exact rules/version used by a league-season score.

    A later settings edit creates a distinct policy snapshot rather than
    retroactively changing the evidence behind an already-calculated score.
    """
    rules = scoring_rules or {}
    rules_hash = _policy_hash(rules)
    existing = (
        db.query(LeagueScoringSnapshot)
        .filter(
            LeagueScoringSnapshot.league_id == league_id,
            LeagueScoringSnapshot.season == season,
            LeagueScoringSnapshot.rules_sha256 == rules_hash,
            LeagueScoringSnapshot.calculation_version == CALCULATION_VERSION,
        )
        .one_or_none()
    )
    if existing:
        return existing
    snapshot = LeagueScoringSnapshot(
        league_id=league_id,
        season=season,
        rules_json=rules,
        rules_sha256=rules_hash,
        calculation_version=CALCULATION_VERSION,
        locked_at=utcnow(),
        created_at=utcnow(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def calculate_snapshot(
    db: Session,
    *,
    league_id: int,
    revision: PlayerGameStatRevision,
    scoring_rules: dict | None,
    publish_state: str | None = None,
) -> ScoringCalculationSnapshot:
    """Calculate once from a complete immutable revision.

    This never writes mutable player/team/matchup totals.  The promotion layer
    is intentionally separate and may run only in explicit ``enabled`` mode.
    """
    if revision.completeness != COMPLETE or revision.status != "accepted":
        raise IncompleteStatRevisionError("cannot calculate a snapshot from an incomplete or blocked revision")
    player = db.get(Player, revision.player_id)
    if player is None:
        raise IdentityResolutionError("canonical player disappeared before calculation")
    points, breakdown = calculate_player_fantasy_points(
        {key: float(value) for key, value in revision.stats_json.items()}, scoring_rules or {}, player.position
    )
    league_snapshot = get_or_create_league_scoring_snapshot(
        db,
        league_id=league_id,
        season=revision.season,
        scoring_rules=scoring_rules,
    )
    policy_hash = league_snapshot.rules_sha256
    key = f"{league_id}:{league_snapshot.id}:{revision.id}:{CALCULATION_VERSION}"
    existing = db.query(ScoringCalculationSnapshot).filter(ScoringCalculationSnapshot.idempotency_key == key).one_or_none()
    if existing:
        return existing
    state = publish_state or ("published" if settings.scoring_mode == "enabled" else "shadow")
    if state == "published" and settings.scoring_mode != "enabled":
        raise LiveScoringContractError("public scoring snapshot promotion is disabled in this runtime")
    snapshot = ScoringCalculationSnapshot(
        stat_revision_id=revision.id,
        league_scoring_snapshot_id=league_snapshot.id,
        raw_event_id=revision.raw_event_id,
        league_id=league_id,
        player_id=revision.player_id,
        season=revision.season,
        week=revision.week,
        scorer_version=CALCULATION_VERSION,
        scoring_policy_hash=policy_hash,
        score=points,
        breakdown_json=breakdown,
        publish_state=state,
        idempotency_key=key,
        calculated_at=utcnow(),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def enqueue_work(
    db: Session,
    *,
    task_type: str,
    idempotency_key: str,
    payload: dict[str, Any],
    max_attempts: int | None = None,
) -> ScoringWorkItem:
    existing = db.query(ScoringWorkItem).filter(ScoringWorkItem.idempotency_key == idempotency_key).one_or_none()
    if existing:
        return existing
    item = ScoringWorkItem(
        task_type=task_type,
        idempotency_key=idempotency_key,
        payload_json=payload,
        max_attempts=max_attempts or settings.scoring_worker_retry_max_attempts,
        next_attempt_at=utcnow(),
    )
    db.add(item)
    db.flush()
    return item


def lease_next_work_item(db: Session, *, worker_id: str, lease_seconds: int = 60) -> ScoringWorkItem | None:
    now = utcnow()
    item = (
        db.query(ScoringWorkItem)
        .filter(
            or_(ScoringWorkItem.status == "pending", ScoringWorkItem.status == "leased"),
            or_(ScoringWorkItem.next_attempt_at.is_(None), ScoringWorkItem.next_attempt_at <= now),
            or_(ScoringWorkItem.lease_expires_at.is_(None), ScoringWorkItem.lease_expires_at <= now),
        )
        .order_by(ScoringWorkItem.id.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if item is None:
        return None
    item.status = "leased"
    item.attempts += 1
    item.lease_owner = worker_id
    item.lease_expires_at = now + timedelta(seconds=lease_seconds)
    db.flush()
    return item


def complete_work_item(db: Session, item: ScoringWorkItem, *, worker_id: str) -> None:
    if item.status != "leased" or item.lease_owner != worker_id:
        raise LiveScoringContractError("only the current lease holder may complete a scoring work item")
    item.status = "succeeded"
    item.completed_at = utcnow()
    item.lease_owner = None
    item.lease_expires_at = None
    db.flush()


def fail_work_item(
    db: Session,
    item: ScoringWorkItem,
    *,
    worker_id: str,
    category: str,
    message: str,
) -> None:
    if item.status != "leased" or item.lease_owner != worker_id:
        raise LiveScoringContractError("only the current lease holder may fail a scoring work item")
    item.last_error_category = category
    item.last_error_message = message[:4000]
    item.lease_owner = None
    item.lease_expires_at = None
    if item.attempts >= item.max_attempts:
        item.status = "dead_letter"
        db.add(
            ScoringDeadLetter(
                work_item_id=item.id,
                failure_category=category,
                failure_message=message[:4000],
                failed_at=utcnow(),
            )
        )
    else:
        item.status = "pending"
        item.next_attempt_at = utcnow() + timedelta(seconds=max(1, settings.scoring_worker_retry_base_seconds * item.attempts))
    db.flush()


def replay_dead_letter(db: Session, *, dead_letter_id: int) -> ScoringWorkItem:
    """Explicitly replay a reviewed dead-lettered work item.

    Replays are an operator action, never an automatic side effect.  The
    original dead-letter evidence remains intact and records when it was
    replayed; the same idempotency key prevents a duplicate public result.
    """
    dead_letter = db.get(ScoringDeadLetter, dead_letter_id)
    if dead_letter is None:
        raise LiveScoringContractError("scoring dead-letter record does not exist")
    if dead_letter.replayed_at is not None:
        raise LiveScoringContractError("scoring dead-letter has already been replayed")
    item = db.get(ScoringWorkItem, dead_letter.work_item_id)
    if item is None or item.status != "dead_letter":
        raise LiveScoringContractError("dead-letter does not reference a replayable work item")
    item.status = "pending"
    item.attempts = 0
    item.lease_owner = None
    item.lease_expires_at = None
    item.next_attempt_at = utcnow()
    item.last_error_category = None
    item.last_error_message = None
    dead_letter.replayed_at = utcnow()
    db.flush()
    return item


def process_one_scoring_work_item(db: Session, *, worker_id: str) -> ScoringWorkItem | None:
    """Process one durable scoring task without contacting a provider.

    Provider polling is intentionally outside this worker.  An approved
    adapter must first record a verified raw event and revision, then enqueue
    this work item.  That makes retries and replays deterministic and keeps a
    worker restart from fetching or re-applying an unbounded provider feed.
    """
    item = lease_next_work_item(db, worker_id=worker_id)
    if item is None:
        return None
    try:
        if item.task_type == "score_revision":
            revision_id = item.payload_json.get("revision_id")
            league_id = item.payload_json.get("league_id")
            if not isinstance(revision_id, int) or not isinstance(league_id, int):
                raise LiveScoringContractError("score_revision requires integer revision_id and league_id")
            revision = db.get(PlayerGameStatRevision, revision_id)
            if revision is None:
                raise LiveScoringContractError("score_revision references a missing stat revision")
            league_settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).one_or_none()
            calculate_snapshot(
                db,
                league_id=league_id,
                revision=revision,
                scoring_rules=league_settings.scoring_json if league_settings else {},
            )
            # Build a separate immutable projection after the score snapshot is
            # durable.  The task is idempotent per correction revision and
            # never changes legacy public score/matchup/standing rows.
            enqueue_work(
                db,
                task_type="rebuild_shadow_read_model",
                idempotency_key=f"shadow-read-model:{league_id}:{revision.season}:{revision.week}:{revision.id}",
                payload={"league_id": league_id, "season": revision.season, "week": revision.week},
            )
        elif item.task_type == "rebuild_shadow_read_model":
            league_id = item.payload_json.get("league_id")
            season = item.payload_json.get("season")
            week = item.payload_json.get("week")
            if not all(isinstance(value, int) for value in (league_id, season, week)):
                raise LiveScoringContractError(
                    "rebuild_shadow_read_model requires integer league_id, season, and week"
                )
            # Local import prevents a service-level circular dependency while
            # keeping the worker's only effect confined to immutable shadow
            # evidence.
            from collegefootballfantasy_api.app.services.live_scoring_read_model_service import (
                build_shadow_read_model,
                persist_shadow_read_model,
            )

            persist_shadow_read_model(
                db,
                build_shadow_read_model(db, league_id=league_id, season=season, week=week),
            )
        else:
            raise LiveScoringContractError(f"unsupported scoring work item: {item.task_type}")
        complete_work_item(db, item, worker_id=worker_id)
        return item
    except Exception as exc:
        fail_work_item(
            db,
            item,
            worker_id=worker_id,
            category=exc.__class__.__name__,
            message=str(exc),
        )
        raise
