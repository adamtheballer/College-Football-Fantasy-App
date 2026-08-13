"""Append-only, idempotent live-scoring pipeline services.

Nothing in this module fetches a provider or mutates public score read models.
The caller records a provider event, verifies exact provider identities, stores
an immutable stat revision, and can then calculate a shadow/public snapshot.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.live_scoring_contract import (
    CANCELED,
    COMPLETE,
    DELAYED,
    FINAL_UNVERIFIED,
    FINAL_VERIFIED,
    HALFTIME,
    IN_PROGRESS,
    POSTPONED,
    SUSPENDED,
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
    ProviderGamePollState,
    ProviderPollingHealth,
    ProviderRawEvent,
    ScoringCalculationSnapshot,
    ScoringCorrectionLedger,
    ScoringDeadLetter,
    ScoringWorkItem,
)
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.provider_identity import UnmatchedProviderRow
from collegefootballfantasy_api.app.models.roster import RosterEntry


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
    provider_player_id: str | None = None,
    provider_game_id: str | None = None,
) -> PlayerGameStatRevision:
    """Record one immutable, exact-identity provider stat revision.

    Incomplete payloads are saved as blocked evidence, but cannot be used for
    a score.  This preserves forensic input without converting omitted values
    to zero.
    """
    if lifecycle_state not in VALID_GAME_LIFECYCLES:
        raise LiveScoringContractError("invalid game lifecycle state")
    resolved_player_id = provider_player_id or raw_event.provider_player_id
    resolved_game_id = provider_game_id or raw_event.provider_game_id
    if not resolved_player_id or not resolved_game_id:
        raise IdentityResolutionError("stat revisions require exact provider player and game ids")
    player_id = resolve_exact_player_id(
        db, provider=raw_event.provider, provider_player_id=resolved_player_id
    )
    game_id = resolve_exact_game_id(db, provider=raw_event.provider, provider_game_id=resolved_game_id)
    # ESPN stat groups are position-specific.  Resolve the canonical position
    # only after the exact provider identity succeeds; never infer it from a
    # name or a provider team label.
    if position is None:
        player = db.get(Player, player_id)
        if player is None:
            raise IdentityResolutionError("canonical player disappeared before stat normalization")
        position = player.position
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
            PlayerGameStatRevision.provider_player_id == resolved_player_id,
            PlayerGameStatRevision.provider_game_id == resolved_game_id,
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
        provider_player_id=resolved_player_id,
        provider_game_id=resolved_game_id,
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


def _record_unmatched_athlete(
    db: Session,
    *,
    provider_player_id: str,
    provider_team_id: str | None,
    provider_game_id: str,
    athlete_name: str | None,
    season: int,
    week: int,
) -> None:
    """Persist the identity gap as operator work; never fuzzy-match a name."""
    payload = {"provider_player_id": provider_player_id, "provider_game_id": provider_game_id}
    key = sha256({"provider": "espn", "feed": "live_boxscore", **payload})
    row = db.query(UnmatchedProviderRow).filter(
        UnmatchedProviderRow.provider == "espn",
        UnmatchedProviderRow.feed == "live_boxscore",
        UnmatchedProviderRow.dedupe_hash == key,
    ).one_or_none()
    if row:
        row.occurrence_count += 1
        row.last_seen_at = utcnow()
        return
    db.add(UnmatchedProviderRow(
        provider="espn", feed="live_boxscore", season=season, week=week,
        provider_player_id=provider_player_id, provider_team_id=provider_team_id,
        player_name=athlete_name, dedupe_hash=key, raw_payload=payload,
        status="identity_unmatched", last_seen_at=utcnow(), notes="IDENTITY_UNMATCHED",
    ))


def _shadow_league_ids_for_player(db: Session, *, player_id: int) -> list[int]:
    return [league_id for (league_id,) in db.query(RosterEntry.league_id).filter(RosterEntry.player_id == player_id).distinct()]


def _poll_delay_seconds(state: str, stage: str) -> int | None:
    if state in {POSTPONED, CANCELED}:
        return None
    if state in {IN_PROGRESS, HALFTIME, DELAYED, SUSPENDED}:
        return settings.espn_live_scoring_active_poll_interval_seconds
    if state == FINAL_UNVERIFIED:
        if stage == "normal":
            return 0
        if stage == "immediate":
            return settings.espn_live_scoring_postgame_first_delay_seconds
        if stage == "plus_10m":
            return settings.espn_live_scoring_postgame_second_delay_seconds
        if stage == "plus_2h":
            return settings.espn_live_scoring_next_day_delay_seconds
        return None
    return settings.espn_live_scoring_scoreboard_interval_seconds


def _advance_final_stage(stage: str) -> str:
    return {"normal": "immediate", "immediate": "plus_10m", "plus_10m": "plus_2h", "plus_2h": "next_day"}.get(stage, stage)


def ensure_relevant_espn_poll_states(db: Session, *, season: int, week: int) -> int:
    """Register only reviewed ESPN-to-canonical game mappings for due polling.

    This deliberately does not discover or create mappings by school/name;
    reviewed ``ProviderGameIdentity`` rows are the hard boundary.
    """
    created = 0
    identities = db.query(ProviderGameIdentity).filter(
        ProviderGameIdentity.provider == "espn", ProviderGameIdentity.verification_status == "verified"
    ).all()
    from collegefootballfantasy_api.app.models.game import Game
    for identity in identities:
        game = db.get(Game, identity.game_id)
        if game is None or game.season != season or game.week != week:
            continue
        # Do not turn ESPN's full scoreboard into our polling queue.  A game
        # is relevant only when it contains a player currently represented in
        # a fantasy roster or a canonical draftable player.  This uses exact
        # canonical school fields solely to decide *which known game mapping*
        # is worth polling; it never establishes an ESPN identity mapping.
        relevant_player = (
            db.query(Player.id)
            .outerjoin(RosterEntry, RosterEntry.player_id == Player.id)
            .filter(
                Player.school.in_((game.home_team, game.away_team)),
                or_(RosterEntry.id.is_not(None), Player.cfb27_rank.is_not(None)),
            )
            .first()
        )
        if relevant_player is None:
            continue
        exists = db.query(ProviderGamePollState).filter(
            ProviderGamePollState.provider == "espn", ProviderGamePollState.provider_game_id == identity.provider_game_id
        ).one_or_none()
        if exists is None:
            db.add(ProviderGamePollState(provider="espn", provider_game_id=identity.provider_game_id, game_id=game.id,
                season=season, week=week, lifecycle_state="scheduled", final_fetch_stage="normal", next_poll_at=utcnow()))
            created += 1
    db.flush()
    return created


def claim_due_espn_poll_states(db: Session, *, season: int, week: int, now: datetime | None = None) -> list[dict[str, Any]]:
    """Claim due polls in a short transaction; callers fetch after commit."""
    now = now or utcnow()
    health = db.query(ProviderPollingHealth).filter(ProviderPollingHealth.provider == "espn").one_or_none()
    if health and health.blocked_until and health.blocked_until > now:
        return []
    due = db.query(ProviderGamePollState).filter(
        ProviderGamePollState.provider == "espn", ProviderGamePollState.season == season,
        ProviderGamePollState.week == week, ProviderGamePollState.next_poll_at.is_not(None),
        ProviderGamePollState.next_poll_at <= now,
        ProviderGamePollState.lifecycle_state.in_({IN_PROGRESS, HALFTIME, DELAYED, SUSPENDED, FINAL_UNVERIFIED}),
        or_(ProviderGamePollState.rate_limited_until.is_(None), ProviderGamePollState.rate_limited_until <= now),
    ).with_for_update(skip_locked=True).all()
    claimed: list[dict[str, Any]] = []
    for state in due:
        state.last_polled_at = now
        # A short lease prevents another worker from fetching the same game
        # while this worker is outside the database transaction.
        state.next_poll_at = now + timedelta(seconds=max(30, settings.espn_live_scoring_timeout_seconds * 2))
        claimed.append({"state_id": state.id, "game_id": state.provider_game_id, "season": state.season, "week": state.week})
    db.flush()
    return claimed


def scoreboard_refresh_due(db: Session, *, season: int, week: int, now: datetime | None = None) -> bool:
    """Return whether the shared ESPN scoreboard is due without making a request.

    The caller commits this tiny read/update transaction before doing the
    network request.  A scoreboard is global to the relevant games, never a
    per-league or per-player fetch.
    """
    now = now or utcnow()
    cutoff = now - timedelta(seconds=settings.espn_live_scoring_scoreboard_interval_seconds)
    return (
        db.query(ProviderGamePollState.id)
        .filter(
            ProviderGamePollState.provider == "espn",
            ProviderGamePollState.season == season,
            ProviderGamePollState.week == week,
            or_(ProviderGamePollState.last_scoreboard_at.is_(None), ProviderGamePollState.last_scoreboard_at <= cutoff),
        )
        .first()
        is not None
    )


def ingest_espn_scoreboard(db: Session, *, games: list[Any] | tuple[Any, ...]) -> int:
    """Record one structured scoreboard response for each known canonical game.

    Schedule discovery does not create identity mappings: an ESPN game must
    already have a reviewed ``ProviderGameIdentity`` row to update a poll
    state.  This is the hard no-fuzzy-match boundary for live scoring.
    """
    now = utcnow()
    ingested = 0
    for game in games:
        state = (
            db.query(ProviderGamePollState)
            .filter(
                ProviderGamePollState.provider == "espn",
                ProviderGamePollState.provider_game_id == game.game_id,
            )
            .one_or_none()
        )
        if state is None:
            continue
        event = record_provider_event(
            db,
            ProviderEventInput(
                provider="espn",
                feed="live_scoreboard",
                event_type="scoreboard_status",
                endpoint_type="scoreboard",
                provider_event_id=f"espn:scoreboard:{game.game_id}:{sha256(game.payload)}",
                request_key=f"scoreboard:{game.season}:{game.week}",
                http_status=200,
                season=game.season,
                week=game.week,
                provider_game_id=game.game_id,
                payload=game.payload,
            ),
        )
        state.lifecycle_state = game.status
        state.last_scoreboard_at = now
        if game.status in {IN_PROGRESS, HALFTIME, DELAYED, SUSPENDED, FINAL_UNVERIFIED}:
            # The next worker loop (roughly 30 seconds) claims the detailed
            # box score. No detailed request is made before kickoff.
            state.next_poll_at = now
        elif game.status in {POSTPONED, CANCELED}:
            state.next_poll_at = None
        event.processing_status = "processed"
        event.processed_at = now
        ingested += 1
    db.flush()
    return ingested


def record_espn_poll_failure(
    db: Session, *, state_id: int, category: str, message: str, status_code: int | None = None, retry_after: int | None = None
) -> None:
    now = utcnow()
    state = db.get(ProviderGamePollState, state_id)
    if state is None:
        return
    health = db.query(ProviderPollingHealth).filter(ProviderPollingHealth.provider == "espn").one_or_none()
    if health is None:
        # SQLAlchemy column defaults are applied at INSERT time, not while a
        # newly created object is still being used in this transaction.
        health = ProviderPollingHealth(
            provider="espn",
            circuit_state="closed",
            consecutive_failures=0,
        )
        db.add(health)
    state.failure_count += 1
    state.last_error_category = category
    state.last_error_message = message[:4000]
    health.consecutive_failures += 1
    health.last_error_category = category
    health.last_error_message = message[:4000]
    health.last_http_status = status_code
    health.last_failure_at = now
    if category == "RATE_LIMITED":
        delay = retry_after or settings.espn_live_scoring_circuit_breaker_cooldown_seconds
        state.rate_limited_until = now + timedelta(seconds=delay)
        health.circuit_state = "open"
        health.blocked_until = now + timedelta(seconds=delay)
    elif category == "PROVIDER_BLOCKED":
        state.operator_status = "provider_blocked"
        state.next_poll_at = None
        health.circuit_state = "open"
        health.blocked_until = now + timedelta(seconds=settings.espn_live_scoring_circuit_breaker_cooldown_seconds)
    elif health.consecutive_failures >= settings.espn_live_scoring_circuit_breaker_failures:
        health.circuit_state = "open"
        health.blocked_until = now + timedelta(seconds=settings.espn_live_scoring_circuit_breaker_cooldown_seconds)
    else:
        # ESPN's normal 5xx retry sequence is 3m, 6m, then 12m.  A bounded
        # jitter avoids a fleet of workers retrying at the same instant.
        retry_seconds = settings.espn_live_scoring_active_poll_interval_seconds * (2 ** min(state.failure_count - 1, 2))
        state.next_poll_at = now + timedelta(seconds=retry_seconds + random.randint(0, min(30, retry_seconds)))
    db.flush()


def record_espn_provider_outage(
    db: Session,
    *,
    category: str,
    message: str,
    status_code: int | None = None,
    retry_after: int | None = None,
) -> None:
    """Record provider-wide scoreboard failure without inventing game state.

    The scoreboard is a single global request, so it has no claimed game row
    to attach to.  This maintains the same circuit breaker used by detailed
    game requests and leaves every canonical game untouched until ESPN is
    reachable again.
    """
    now = utcnow()
    health = db.query(ProviderPollingHealth).filter(ProviderPollingHealth.provider == "espn").one_or_none()
    if health is None:
        health = ProviderPollingHealth(provider="espn")
        db.add(health)
    health.consecutive_failures += 1
    health.last_error_category = category
    health.last_error_message = message[:4000]
    health.last_http_status = status_code
    health.last_failure_at = now
    if category == "RATE_LIMITED":
        delay = retry_after or settings.espn_live_scoring_circuit_breaker_cooldown_seconds
    elif category == "PROVIDER_BLOCKED":
        delay = settings.espn_live_scoring_circuit_breaker_cooldown_seconds
    elif health.consecutive_failures >= settings.espn_live_scoring_circuit_breaker_failures:
        delay = settings.espn_live_scoring_circuit_breaker_cooldown_seconds
    else:
        db.flush()
        return
    health.circuit_state = "open"
    health.blocked_until = now + timedelta(seconds=delay)
    db.flush()


def queue_manual_espn_poll(
    db: Session,
    *,
    season: int,
    week: int,
    cooldown_seconds: int = 30,
) -> int:
    """Queue a bounded admin-requested retry without fetching in the API.

    The route calling this function is admin-only.  It never bypasses the
    provider circuit breaker and it can only move existing, reviewed game
    rows forward to the worker; it cannot create an identity mapping.
    """
    if not settings.espn_live_scoring_enabled or not settings.scoring_shadow_enabled:
        raise LiveScoringContractError("ESPN shadow polling is disabled")
    now = utcnow()
    health = db.query(ProviderPollingHealth).filter(ProviderPollingHealth.provider == "espn").one_or_none()
    if health and health.blocked_until and health.blocked_until > now:
        raise LiveScoringContractError("ESPN provider circuit breaker is open")
    states = db.query(ProviderGamePollState).filter(
        ProviderGamePollState.provider == "espn",
        ProviderGamePollState.season == season,
        ProviderGamePollState.week == week,
        ProviderGamePollState.lifecycle_state.in_({IN_PROGRESS, HALFTIME, DELAYED, SUSPENDED, FINAL_UNVERIFIED}),
    ).all()
    queued = 0
    for state in states:
        if state.last_polled_at and state.last_polled_at > now - timedelta(seconds=cooldown_seconds):
            continue
        state.next_poll_at = now
        state.operator_status = "manual_requested"
        queued += 1
    db.flush()
    return queued


def ingest_espn_game_summary(db: Session, *, state_id: int, summary: Any) -> dict[str, int]:
    """Persist one complete ESPN game response and fan it out to shadow work."""
    state = db.get(ProviderGamePollState, state_id)
    if state is None:
        raise LiveScoringContractError("claimed ESPN poll state no longer exists")
    event = record_provider_event(db, ProviderEventInput(
        provider="espn", feed="live_boxscore", event_type="game_boxscore", endpoint_type="game_summary",
        provider_event_id=f"espn:{summary.game.game_id}:{sha256(summary.payload)}", request_key=f"summary:{summary.game.game_id}",
        http_status=200, season=summary.game.season, week=summary.game.week,
        provider_game_id=summary.game.game_id, payload=summary.payload,
    ))
    revisions = unmatched = 0
    for line in summary.athlete_lines:
        try:
            revision = record_stat_revision(db, raw_event=event, provider_player_id=line.athlete_id,
                provider_game_id=summary.game.game_id, position=None, season=summary.game.season, week=summary.game.week,
                lifecycle_state=summary.game.status, completeness=line.completeness, stats=line.stats)
        except IdentityResolutionError:
            _record_unmatched_athlete(db, provider_player_id=line.athlete_id, provider_team_id=line.team_id,
                provider_game_id=summary.game.game_id, athlete_name=line.athlete_name, season=summary.game.season, week=summary.game.week)
            unmatched += 1
            continue
        revisions += 1
        for league_id in _shadow_league_ids_for_player(db, player_id=revision.player_id):
            enqueue_work(db, task_type="score_revision", idempotency_key=f"score-revision:{league_id}:{revision.id}",
                payload={"league_id": league_id, "revision_id": revision.id})
    now = utcnow()
    state.lifecycle_state = summary.game.status
    state.last_success_at = now
    state.failure_count = 0
    state.last_error_category = None
    state.last_error_message = None
    final_stage_before_fetch = state.final_fetch_stage
    delay = _poll_delay_seconds(summary.game.status, final_stage_before_fetch)
    if summary.game.status == FINAL_UNVERIFIED:
        state.final_fetch_stage = _advance_final_stage(state.final_fetch_stage)
    state.next_poll_at = now + timedelta(seconds=delay) if delay is not None else None
    health = db.query(ProviderPollingHealth).filter(ProviderPollingHealth.provider == "espn").one_or_none()
    if health is None:
        health = ProviderPollingHealth(provider="espn")
        db.add(health)
    health.circuit_state, health.consecutive_failures, health.blocked_until = "closed", 0, None
    health.last_success_at = now
    event.processing_status, event.processed_at = "processed", now
    certification = None
    if summary.game.status == FINAL_UNVERIFIED and final_stage_before_fetch == "next_day":
        certification = certify_espn_game_final(db, state_id=state.id)
    db.flush()
    return {
        "raw_event_id": event.id,
        "revisions": revisions,
        "identity_unmatched": unmatched,
        "final_certified": int(bool(certification and certification["certified"])),
    }


def certify_espn_game_final(db: Session, *, state_id: int) -> dict[str, Any]:
    """Certify a final ESPN game only after its correction window closes.

    Certification is a shadow-mode audit flag, not a public scoring action.
    Any rostered player from either canonical school without a verified ESPN
    identity or a complete revision remains an explicit blocker.
    """
    state = db.get(ProviderGamePollState, state_id)
    if state is None:
        raise LiveScoringContractError("ESPN poll state disappeared before final certification")
    if state.lifecycle_state != FINAL_UNVERIFIED:
        return {"certified": state.lifecycle_state == FINAL_VERIFIED, "blockers": []}
    from collegefootballfantasy_api.app.models.game import Game

    game = db.get(Game, state.game_id)
    if game is None:
        raise LiveScoringContractError("canonical game disappeared before final certification")
    rostered_player_ids = [
        player_id
        for (player_id,) in db.query(RosterEntry.player_id)
        .join(Player, Player.id == RosterEntry.player_id)
        .filter(
            RosterEntry.status.in_({"active", "starter", "bench", "ir"}),
            Player.school.in_({game.home_team, game.away_team}),
        )
        .distinct()
    ]
    blockers: list[dict[str, Any]] = []
    for player_id in rostered_player_ids:
        identity = (
            db.query(PlayerProviderId)
            .filter(
                PlayerProviderId.player_id == player_id,
                PlayerProviderId.provider == "espn",
                PlayerProviderId.verification_status == "verified",
            )
            .one_or_none()
        )
        if identity is None:
            blockers.append({"player_id": player_id, "reason": "IDENTITY_UNMATCHED"})
            continue
        revision = _latest_revision(db, player_id=player_id, game_id=game.id)
        if revision is None:
            blockers.append({"player_id": player_id, "reason": "MISSING_FINAL_STAT_REVISION"})
        elif revision.status != "accepted" or revision.completeness != COMPLETE:
            blockers.append({"player_id": player_id, "reason": "INCOMPLETE_FINAL_STAT_REVISION"})
    if blockers:
        state.operator_status = "final_verification_blocked"
        return {"certified": False, "blockers": blockers}
    state.lifecycle_state = FINAL_VERIFIED
    state.operator_status = "final_verified"
    state.next_poll_at = None
    return {"certified": True, "blockers": []}


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
