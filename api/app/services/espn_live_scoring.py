"""ESPN alpha live-scoring orchestration.

This module deliberately separates external provider work from fantasy reads.
The only ESPN HTTP calls happen in the worker path; UI/API requests read the
database.  Shadow mode persists immutable provider snapshots but cannot touch
public PlayerStat, matchup, standing, or notification state.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.integrations.espn import (
    ESPNClient,
    ESPNProviderResponse,
    extract_espn_long_play_alert_candidates,
    extract_espn_play_ids,
    extract_player_box_score_stats,
)
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll, ProviderGameSnapshot
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.espn_stats_sync import (
    normalize_espn_summary_player_stats,
    persist_normalized_espn_player_stats,
)
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school


ESPN_PROVIDER = "espn"
MIN_GAME_POLL_INTERVAL_SECONDS = 180
PRE_KICKOFF_POLL_INTERVAL_SECONDS = 900
DEFAULT_GAME_LEASE_SECONDS = 120
DISCOVERY_INTERVAL_SECONDS = 180
FINAL_RECONCILIATION_INTERVAL_SECONDS = 900
BLOCKED_PROVIDER_RETRY_SECONDS = 6 * 60 * 60

LiveScoringMode = Literal["shadow", "enabled"]
SnapshotClassification = Literal["DUPLICATE", "NEWER", "STALE", "AMBIGUOUS", "VERIFIED_CORRECTION"]


class ProviderDataIncompleteError(RuntimeError):
    """An ESPN response cannot safely replace the last verified game totals."""


@dataclass(frozen=True)
class ClaimedGame:
    id: int
    provider_game_id: str
    season: int
    week: int


@dataclass(frozen=True)
class SnapshotOrderMetadata:
    """Only explicit, documented provider order markers belong here.

    ESPN currently supplies no such marker on its public summary endpoint.
    Response receipt time, HTTP Date, ETag, and Last-Modified are audit data,
    never ordering evidence.
    """

    provider_revision: str | None
    provider_updated_at: datetime | None
    provider_etag: str | None
    response_metadata: dict[str, str]
    event_period: int | None
    event_clock: str | None
    event_state: str


@dataclass(frozen=True)
class SnapshotOrderDecision:
    classification: SnapshotClassification
    accepted: bool
    reason: str | None = None

    @property
    def verified_final_correction(self) -> bool:
        return self.classification == "VERIFIED_CORRECTION"


@dataclass(frozen=True)
class EspnCycleResult:
    discovered_games: int
    claimed_games: int
    successful_games: int
    failed_games: int
    normalized_rows: int
    unmatched_rows: int
    promoted_rows: int


@dataclass(frozen=True)
class EspnFreshness:
    provider: str | None
    state: str
    provider_as_of: datetime | None
    last_successful_update_at: datetime | None
    data_age_seconds: int | None
    relevant_game_count: int


def _school_key(value: str | None) -> str | None:
    if not value:
        return None
    return canonical_school_name(value) or normalize_school(value) or _identity(value)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _event_status(event: dict[str, Any]) -> str:
    status = event.get("status")
    if not isinstance(status, dict):
        competitions = event.get("competitions")
        if isinstance(competitions, list) and competitions and isinstance(competitions[0], dict):
            status = competitions[0].get("status")
    status = status if isinstance(status, dict) else {}
    status_type = status.get("type") if isinstance(status.get("type"), dict) else {}
    name = str(status_type.get("name") or status_type.get("state") or status.get("type") or "").lower()
    completed = bool(status_type.get("completed") or status.get("completed"))
    if completed or name in {"final", "post", "postponed", "canceled", "cancelled"}:
        return "final" if name not in {"postponed", "canceled", "cancelled"} else name
    if name in {"in", "live", "in_progress", "in progress"}:
        return "live"
    return "scheduled"


def _summary_status(summary: dict[str, Any], fallback: str) -> str:
    header = summary.get("header")
    if not isinstance(header, dict):
        return fallback
    return _event_status(header)


def _summary_status_payload(summary: dict[str, Any]) -> dict[str, Any]:
    header = summary.get("header")
    if not isinstance(header, dict):
        return {}
    competitions = header.get("competitions")
    if not isinstance(competitions, list) or not competitions or not isinstance(competitions[0], dict):
        return {}
    status = competitions[0].get("status")
    return status if isinstance(status, dict) else {}


def _parse_period(value: object) -> int | None:
    try:
        period = int(value)  # ESPN sends a numeric period for live games.
    except (TypeError, ValueError):
        return None
    return period if period >= 0 else None


def _parse_clock_seconds(value: str | None) -> int | None:
    if not value or not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    minutes, seconds = (int(part) for part in parts)
    return minutes * 60 + seconds if 0 <= seconds < 60 else None


def _provider_order_metadata(summary: dict[str, Any], response_metadata: dict[str, str] | None = None) -> SnapshotOrderMetadata:
    """Extract only verified game-progress data from ESPN's summary body.

    The public ESPN endpoint observed on 2026-08-16 exposes no documented
    monotonic revision or provider update timestamp.  A future adapter may
    deliberately provide ``provider_revision`` / ``provider_updated_at`` in
    response metadata after their provider semantics are verified.  We do not
    infer either from generic JSON names or HTTP transport headers.
    """

    metadata = dict(response_metadata or {})
    status_payload = _summary_status_payload(summary)
    event_state = _summary_status(summary, "scheduled")
    event_period = _parse_period(status_payload.get("period"))
    event_clock = status_payload.get("displayClock") or status_payload.get("clock")
    event_clock = str(event_clock) if event_clock is not None else None
    return SnapshotOrderMetadata(
        provider_revision=metadata.get("provider_revision"),
        provider_updated_at=_parse_datetime(metadata.get("provider_updated_at")),
        provider_etag=metadata.get("etag"),
        response_metadata=metadata,
        event_period=event_period,
        event_clock=event_clock,
        event_state=event_state,
    )


def _revision_comparison(previous: ProviderGameSnapshot, candidate: SnapshotOrderMetadata) -> int | None:
    """Compare only explicit trusted markers; return 1, 0, -1, or unknown."""

    if previous.provider_revision is not None and candidate.provider_revision is not None:
        try:
            before, after = int(previous.provider_revision), int(candidate.provider_revision)
        except ValueError:
            return None
        return (after > before) - (after < before)
    if previous.provider_updated_at is not None and candidate.provider_updated_at is not None:
        before = _as_utc(previous.provider_updated_at)
        after = _as_utc(candidate.provider_updated_at)
        assert before is not None and after is not None
        return (after > before) - (after < before)
    return None


def _progress_comparison(previous: ProviderGameSnapshot, candidate: SnapshotOrderMetadata) -> int | None:
    """Compare verified game progression without treating payload content as time."""

    rank = {"scheduled": 0, "live": 1, "final": 2}
    previous_state = previous.event_state or previous.status
    candidate_state = candidate.event_state
    previous_rank = rank.get(previous_state)
    candidate_rank = rank.get(candidate_state)
    if previous_rank is None or candidate_rank is None:
        return None
    if candidate_rank != previous_rank:
        return (candidate_rank > previous_rank) - (candidate_rank < previous_rank)
    if candidate_state != "live":
        return 0
    if previous.event_period is None or candidate.event_period is None:
        return None
    if candidate.event_period != previous.event_period:
        return (candidate.event_period > previous.event_period) - (candidate.event_period < previous.event_period)
    previous_clock = _parse_clock_seconds(previous.event_clock)
    candidate_clock = _parse_clock_seconds(candidate.event_clock)
    if previous_clock is None or candidate_clock is None:
        return None
    # ESPN's displayClock is remaining game time.  A lower value in the same
    # period is later; a higher value is an older provider response.
    return (previous_clock > candidate_clock) - (previous_clock < candidate_clock)


def classify_snapshot_order(
    previous: ProviderGameSnapshot | None,
    *,
    candidate_hash: str,
    candidate: SnapshotOrderMetadata,
) -> SnapshotOrderDecision:
    """Fail closed: content difference alone is never proof of newer data."""

    if previous is None:
        return SnapshotOrderDecision("NEWER", True, "initial_complete_snapshot")
    if previous.snapshot_hash == candidate_hash:
        return SnapshotOrderDecision("DUPLICATE", False, "identical_accepted_payload")

    revision_comparison = _revision_comparison(previous, candidate)
    if revision_comparison is not None:
        if revision_comparison < 0:
            return SnapshotOrderDecision("STALE", False, "provider_revision_regressed")
        if revision_comparison == 0:
            return SnapshotOrderDecision("AMBIGUOUS", False, "same_provider_revision_different_payload")
        if (previous.event_state or previous.status) == "final" and candidate.event_state == "final":
            return SnapshotOrderDecision("VERIFIED_CORRECTION", True, "newer_final_provider_revision")
        return SnapshotOrderDecision("NEWER", True, "newer_provider_revision")

    # A final game cannot be reopened by an unordered or regressive response.
    previous_state = previous.event_state or previous.status
    if previous_state == "final":
        if candidate.event_state != "final":
            return SnapshotOrderDecision("STALE", False, "final_state_regression")
        return SnapshotOrderDecision("AMBIGUOUS", False, "ambiguous_final_correction_without_provider_revision")

    progress_comparison = _progress_comparison(previous, candidate)
    if progress_comparison is None:
        return SnapshotOrderDecision("AMBIGUOUS", False, "provider_progress_unavailable")
    if progress_comparison < 0:
        return SnapshotOrderDecision("STALE", False, "provider_game_progress_regressed")
    if progress_comparison == 0:
        return SnapshotOrderDecision("AMBIGUOUS", False, "same_provider_progress_different_payload")
    return SnapshotOrderDecision("NEWER", True, "provider_game_progress_advanced")


def _canonical_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _identity(value: object) -> str:
    return "".join(character for character in str(value or "").lower() if character.isalnum())


def rostered_school_keys(db: Session, *, season: int) -> set[str]:
    """Return schools that can affect an active fantasy roster this season."""

    rows = (
        db.query(Player.school)
        .join(RosterEntry, RosterEntry.player_id == Player.id)
        .join(League, League.id == RosterEntry.league_id)
        .filter(League.season_year == season, RosterEntry.status == "active")
        .distinct()
        .all()
    )
    return {_identity(school) for (school,) in rows if _identity(school)}


def event_team_keys(event: dict[str, Any]) -> set[str]:
    competitions = event.get("competitions")
    if not isinstance(competitions, list) or not competitions or not isinstance(competitions[0], dict):
        return set()
    competitors = competitions[0].get("competitors")
    if not isinstance(competitors, list):
        return set()
    keys: set[str] = set()
    for competitor in competitors:
        team = competitor.get("team") if isinstance(competitor, dict) else None
        if not isinstance(team, dict):
            continue
        for field in ("location", "shortDisplayName", "displayName", "name", "abbreviation"):
            key = _identity(team.get(field))
            if key:
                keys.add(key)
    return keys


def espn_week_freshness(
    db: Session,
    *,
    season: int,
    week: int,
    now: datetime | None = None,
) -> EspnFreshness:
    """Return conservative persisted freshness for the current ESPN week.

    Discovery rows do not represent game data and are excluded.  A missing
    row is explicitly unavailable; it never gets translated into a zero score
    or a falsely reassuring "live" label.
    """

    current = _as_utc(now) or _utc_now()
    rows = (
        db.query(ProviderGamePoll)
        .filter(
            ProviderGamePoll.provider == ESPN_PROVIDER,
            ProviderGamePoll.season == season,
            ProviderGamePoll.week == week,
            ProviderGamePoll.provider_game_id.notlike("discovery:%"),
        )
        .all()
    )
    if not rows:
        return EspnFreshness(None, "unavailable", None, None, None, 0)

    successes = [row for row in rows if row.last_success_at is not None]
    if not successes:
        state = "delayed" if any(row.status in {"delayed", "blocked"} for row in rows) else "unavailable"
        return EspnFreshness(ESPN_PROVIDER, state, None, None, None, len(rows))

    last_success = max((_as_utc(row.last_success_at) for row in successes if row.last_success_at), default=None)
    provider_as_of = max((_as_utc(row.provider_as_of) for row in successes if row.provider_as_of), default=None)
    age = max(0, int((current - last_success).total_seconds())) if last_success else None
    if any(row.status in {"delayed", "blocked"} for row in rows):
        state = "delayed"
    elif age is not None and age > MIN_GAME_POLL_INTERVAL_SECONDS * 2:
        state = "stale"
    else:
        state = "fresh"
    return EspnFreshness(ESPN_PROVIDER, state, provider_as_of, last_success, age, len(rows))


def _provider_game_ids_for_players(
    db: Session,
    *,
    player_ids: set[int],
    season: int,
    week: int,
) -> dict[int, str | None]:
    """Map a starter to one *verified schedule* game id without fuzzy matching.

    ``Game.external_id`` must already be the ESPN event identifier from the
    schedule import.  Missing or ambiguous mappings deliberately block
    automatic fantasy-matchup finality rather than risking a premature final.
    """

    if not player_ids:
        return {}
    player_schools = {
        player_id: _school_key(school)
        for player_id, school in db.query(Player.id, Player.school).filter(Player.id.in_(player_ids)).all()
    }
    game_by_school: dict[str, str | None] = {}
    for game in db.query(Game).filter(Game.season == season, Game.week == week).all():
        if (game.schedule_status or "").strip().lower() in {"cancelled", "canceled", "postponed", "tbd"}:
            continue
        provider_game_id = str(game.external_id or "").strip() or None
        for school in (game.home_team, game.away_team):
            key = _school_key(school)
            if not key:
                continue
            previous = game_by_school.get(key)
            # More than one schedule candidate is not a safe authoritative
            # mapping.  Treat it as unavailable until schedule data is fixed.
            if key not in game_by_school:
                game_by_school[key] = provider_game_id
            elif previous != provider_game_id:
                game_by_school[key] = None
    return {player_id: game_by_school.get(school) if school else None for player_id, school in player_schools.items()}


def certify_espn_matchup_finality(
    db: Session,
    *,
    season: int,
    week: int,
    corrected_provider_game_ids: set[str] | None = None,
) -> int:
    """Certify final fantasy matchups only after every starter's ESPN game final.

    It never uses elapsed time or score shape.  An unknown player-to-game
    mapping, a delayed game, a cancellation, or a non-final provider event is
    a hard stop.  A later changed final snapshot turns an already-certified
    matchup into ``stat_corrected`` so the existing correction/audit path owns
    downstream notifications.
    """

    corrected_provider_game_ids = corrected_provider_game_ids or set()
    changed = 0
    affected_leagues: set[int] = set()
    final_rows = {
        row.provider_game_id: row
        for row in db.query(ProviderGamePoll)
        .filter(
            ProviderGamePoll.provider == ESPN_PROVIDER,
            ProviderGamePoll.season == season,
            ProviderGamePoll.week == week,
            ProviderGamePoll.status == "final",
        )
        .all()
    }
    for matchup in db.query(Matchup).filter(Matchup.season == season, Matchup.week == week).all():
        snapshots = (
            db.query(LineupWeekSnapshot)
            .filter(
                LineupWeekSnapshot.league_id == matchup.league_id,
                LineupWeekSnapshot.season == season,
                LineupWeekSnapshot.week == week,
                LineupWeekSnapshot.team_id.in_((matchup.home_team_id, matchup.away_team_id)),
                LineupWeekSnapshot.is_starter.is_(True),
            )
            .all()
        )
        if not snapshots:
            continue
        game_ids_by_player = _provider_game_ids_for_players(
            db,
            player_ids={snapshot.player_id for snapshot in snapshots},
            season=season,
            week=week,
        )
        provider_game_ids = set(game_ids_by_player.values())
        if None in provider_game_ids or not provider_game_ids or not provider_game_ids.issubset(final_rows):
            continue
        current_status = (matchup.status or "").lower()
        next_status = "stat_corrected" if current_status == "final" and provider_game_ids.intersection(corrected_provider_game_ids) else "final"
        if current_status == next_status:
            continue
        matchup.status = next_status
        changed += 1
        affected_leagues.add(matchup.league_id)
        from collegefootballfantasy_api.app.services.notification_service import queue_certified_matchup_final_notifications

        queue_certified_matchup_final_notifications(db, matchup)
    if changed:
        db.flush()
        # Finality changes standings eligibility.  Score computation has
        # already completed in the caller; only standings need recomputation.
        from collegefootballfantasy_api.app.services.scoring_service import recalculate_standings_for_week

        for league_id in affected_leagues:
            recalculate_standings_for_week(db, league_id, season, week)
        db.commit()
    return changed


def _retry_after_seconds(error: Exception) -> int | None:
    if not isinstance(error, httpx.HTTPStatusError):
        return None
    value = error.response.headers.get("Retry-After")
    try:
        return max(0, int(value)) if value is not None else None
    except ValueError:
        return None


def _failure_policy(error: Exception, *, failure_count: int) -> tuple[str, int]:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 403:
            return "blocked", BLOCKED_PROVIDER_RETRY_SECONDS
        if status == 429:
            retry_after = _retry_after_seconds(error)
            return "delayed", max(MIN_GAME_POLL_INTERVAL_SECONDS, retry_after or 0)
    return "delayed", max(MIN_GAME_POLL_INTERVAL_SECONDS, MIN_GAME_POLL_INTERVAL_SECONDS * (2 ** max(0, failure_count - 1)))


def _is_due(row: ProviderGamePoll, now: datetime) -> bool:
    lease_expires_at = _as_utc(row.lease_expires_at)
    next_poll_at = _as_utc(row.next_poll_at)
    return (lease_expires_at is None or lease_expires_at <= now) and (next_poll_at is None or next_poll_at <= now)


def discovery_due(db: Session, *, season: int, week: int, now: datetime | None = None) -> bool:
    now = _as_utc(now) or _utc_now()
    row = (
        db.query(ProviderGamePoll)
        .filter_by(provider=ESPN_PROVIDER, provider_game_id=f"discovery:{season}:{week}")
        .one_or_none()
    )
    return row is None or _is_due(row, now)


def record_discovery_attempt(
    db: Session,
    *,
    season: int,
    week: int,
    now: datetime,
    success: bool,
    error: Exception | None = None,
) -> None:
    key = f"discovery:{season}:{week}"
    row = db.query(ProviderGamePoll).filter_by(provider=ESPN_PROVIDER, provider_game_id=key).one_or_none()
    if row is None:
        row = ProviderGamePoll(
            provider=ESPN_PROVIDER,
            provider_game_id=key,
            season=season,
            week=week,
            status="scheduled",
        )
        db.add(row)
    row.last_attempt_at = now
    row.lease_owner = None
    row.lease_expires_at = None
    if success:
        row.last_success_at = now
        row.next_poll_at = now + timedelta(seconds=DISCOVERY_INTERVAL_SECONDS)
        row.failure_count = 0
        row.error_message = None
    else:
        row.failure_count += 1
        status, retry_seconds = _failure_policy(error or RuntimeError("ESPN discovery failed"), failure_count=row.failure_count)
        row.status = status
        row.error_message = str(error or "ESPN discovery failed")[:500]
        row.next_poll_at = now + timedelta(seconds=retry_seconds)


def discover_relevant_espn_games(
    db: Session,
    *,
    season: int,
    week: int,
    events: list[dict[str, Any]],
    relevant_team_names: set[str] | None = None,
    now: datetime | None = None,
) -> int:
    """Persist scoreboard discovery; one row represents one ESPN game, not a league."""

    now = _as_utc(now) or _utc_now()
    discovered = 0
    for event in events:
        if relevant_team_names is not None and not event_team_keys(event).intersection(relevant_team_names):
            continue
        provider_game_id = str(event.get("id") or "").strip()
        if not provider_game_id:
            continue
        status = _event_status(event)
        row = db.query(ProviderGamePoll).filter_by(provider=ESPN_PROVIDER, provider_game_id=provider_game_id).one_or_none()
        if row is None:
            row = ProviderGamePoll(
                provider=ESPN_PROVIDER,
                provider_game_id=provider_game_id,
                season=season,
                week=week,
                status=status,
                next_poll_at=now,
            )
            db.add(row)
            discovered += 1
        else:
            row.season = season
            row.week = week
            # A blocked provider path remains blocked until the backoff expires;
            # scoreboard discovery must not accidentally clear that safety
            # state. A stale scoreboard response also cannot reopen a final.
            if row.status != "blocked" and not (row.status == "final" and status != "final"):
                row.status = status
            if status == "final" and row.last_success_at is not None:
                row.next_poll_at = min(
                    _as_utc(row.next_poll_at) or now,
                    now + timedelta(seconds=FINAL_RECONCILIATION_INTERVAL_SECONDS),
                )
    return discovered


def claim_due_espn_games(
    db: Session,
    *,
    season: int,
    week: int,
    worker_id: str | None = None,
    now: datetime | None = None,
    limit: int = 20,
    lease_seconds: int = DEFAULT_GAME_LEASE_SECONDS,
) -> list[ClaimedGame]:
    """Claim due game polls with a durable lease before any HTTP is attempted."""

    now = _as_utc(now) or _utc_now()
    owner = worker_id or f"espn-scoring:{uuid.uuid4()}"
    query = (
        db.query(ProviderGamePoll)
        .filter(
            ProviderGamePoll.provider == ESPN_PROVIDER,
            ProviderGamePoll.season == season,
            ProviderGamePoll.week == week,
            ProviderGamePoll.provider_game_id.notlike("discovery:%"),
            # Scoreboard discovery is the authority for scheduled games.
            # ESPN legitimately omits player box-score rows before kickoff;
            # requesting their summaries treats that normal pregame response
            # as a failure and can falsely mark the entire scoring week stale.
            ProviderGamePoll.status.in_(("live", "final", "delayed")),
            or_(ProviderGamePoll.next_poll_at.is_(None), ProviderGamePoll.next_poll_at <= now),
            or_(ProviderGamePoll.lease_expires_at.is_(None), ProviderGamePoll.lease_expires_at <= now),
        )
        .order_by(ProviderGamePoll.next_poll_at.asc().nullsfirst(), ProviderGamePoll.id.asc())
        .limit(max(1, limit))
        .with_for_update(skip_locked=True)
    )
    rows = query.all()
    claimed: list[ClaimedGame] = []
    for row in rows:
        row.lease_owner = owner
        row.lease_expires_at = now + timedelta(seconds=max(1, lease_seconds))
        row.last_attempt_at = now
        # Reserve the full provider minimum immediately, so a worker crash
        # cannot cause an accidental second request during the 180-second window.
        row.next_poll_at = now + timedelta(seconds=MIN_GAME_POLL_INTERVAL_SECONDS)
        claimed.append(ClaimedGame(row.id, row.provider_game_id, row.season, row.week))
    db.commit()
    return claimed


def _store_snapshot(
    db: Session,
    *,
    row: ProviderGamePoll,
    summary: dict[str, Any],
    normalized_rows: list[dict[str, Any]],
    status: str,
    ordering: SnapshotOrderMetadata,
    decision: SnapshotOrderDecision,
    now: datetime,
) -> ProviderGameSnapshot:
    snapshot_hash = _canonical_hash(summary)
    snapshot = ProviderGameSnapshot(
        provider=ESPN_PROVIDER,
        provider_game_id=row.provider_game_id,
        season=row.season,
        week=row.week,
        status=status,
        provider_as_of=ordering.provider_updated_at,
        captured_at=now,
        provider_revision=ordering.provider_revision,
        provider_updated_at=ordering.provider_updated_at,
        provider_etag=ordering.provider_etag,
        response_metadata=ordering.response_metadata,
        event_period=ordering.event_period,
        event_clock=ordering.event_clock,
        event_state=ordering.event_state,
        classification=decision.classification,
        accepted=decision.accepted,
        rejection_reason=decision.reason if not decision.accepted else None,
        snapshot_hash=snapshot_hash,
        raw_payload=summary,
        normalized_rows=normalized_rows,
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _accepted_snapshot(db: Session, row: ProviderGamePoll) -> ProviderGameSnapshot | None:
    accepted_hash = row.accepted_snapshot_hash or row.latest_snapshot_hash
    if not accepted_hash:
        return None
    snapshot = (
        db.query(ProviderGameSnapshot)
        .filter(
            ProviderGameSnapshot.provider == ESPN_PROVIDER,
            ProviderGameSnapshot.provider_game_id == row.provider_game_id,
            ProviderGameSnapshot.snapshot_hash == accepted_hash,
            ProviderGameSnapshot.accepted.is_(True),
        )
        .order_by(ProviderGameSnapshot.id.desc())
        .first()
    )
    if snapshot is not None:
        return snapshot
    # Rows created before the safety migration have no persisted accepted flag,
    # but the poll's existing hash is still the prior canonical state.
    return (
        db.query(ProviderGameSnapshot)
        .filter(
            ProviderGameSnapshot.provider == ESPN_PROVIDER,
            ProviderGameSnapshot.provider_game_id == row.provider_game_id,
            ProviderGameSnapshot.snapshot_hash == accepted_hash,
        )
        .order_by(ProviderGameSnapshot.id.desc())
        .first()
    )


def queue_accepted_espn_long_play_notifications(
    db: Session,
    *,
    provider_game_id: str,
    summary: dict[str, Any],
    previous_snapshot: ProviderGameSnapshot | None,
) -> int:
    """Queue opted-in player alerts from a newly accepted ESPN snapshot.

    The first accepted snapshot of a game establishes a baseline and never
    backfills alerts.  Later snapshots can only emit for play IDs that were
    absent from that baseline and whose text maps uniquely to a verified
    athlete in the same summary's box score.
    """

    if not settings.live_player_notifications_enabled or previous_snapshot is None:
        return 0
    prior_payload = previous_snapshot.raw_payload if isinstance(previous_snapshot.raw_payload, dict) else {}
    candidates = extract_espn_long_play_alert_candidates(summary, known_play_ids=extract_espn_play_ids(prior_payload))
    if not candidates:
        return 0
    provider_ids = {candidate.provider_player_id for candidate in candidates}
    mappings = {
        mapping.provider_player_id: mapping.player_id
        for mapping in db.query(PlayerProviderId)
        .filter(
            PlayerProviderId.provider == ESPN_PROVIDER,
            PlayerProviderId.provider_player_id.in_(provider_ids),
            PlayerProviderId.verification_status == "verified",
        )
        .all()
    }
    player_ids = set(mappings.values())
    owners_by_player: dict[int, list[tuple[int, int]]] = {}
    if player_ids:
        for league_id, owner_user_id, player_id in (
            db.query(RosterEntry.league_id, Team.owner_user_id, RosterEntry.player_id)
            .join(Team, Team.id == RosterEntry.team_id)
            .filter(RosterEntry.status == "active", RosterEntry.player_id.in_(player_ids), Team.owner_user_id.isnot(None))
            .all()
        ):
            owners_by_player.setdefault(player_id, []).append((league_id, owner_user_id))
    from collegefootballfantasy_api.app.services.notification_service import intake_typed_big_play_notification

    queued = 0
    for candidate in candidates:
        player_id = mappings.get(candidate.provider_player_id)
        if player_id is None:
            continue
        for league_id, user_id in owners_by_player.get(player_id, []):
            event_key = f"big_play:{ESPN_PROVIDER}:{provider_game_id}:{candidate.provider_play_id}:{player_id}:{user_id}"
            if db.query(ScheduledNotification.id).filter(ScheduledNotification.event_key == event_key).first() is not None:
                continue
            notification = intake_typed_big_play_notification(
                db,
                league_id=league_id,
                user_id=user_id,
                event_type=candidate.event_type,
                event_key=event_key,
                player_id=player_id,
                play_yards=candidate.play_yards,
            )
            queued += int(notification is not None)
    return queued


def record_espn_game_success(
    db: Session,
    *,
    claim: ClaimedGame,
    summary: dict[str, Any],
    normalized_rows: list[dict[str, Any]],
    response_metadata: dict[str, str] | None = None,
    now: datetime | None = None,
) -> SnapshotOrderDecision:
    now = _as_utc(now) or _utc_now()
    row = db.get(ProviderGamePoll, claim.id)
    if row is None or row.provider != ESPN_PROVIDER or row.provider_game_id != claim.provider_game_id:
        raise LookupError("claimed ESPN game no longer exists")
    status = _summary_status(summary, row.status)
    ordering = _provider_order_metadata(summary, response_metadata)
    decision = classify_snapshot_order(
        _accepted_snapshot(db, row),
        candidate_hash=_canonical_hash(summary),
        candidate=ordering,
    )
    snapshot = _store_snapshot(
        db,
        row=row,
        summary=summary,
        normalized_rows=normalized_rows,
        status=status,
        ordering=ordering,
        decision=decision,
        now=now,
    )
    row.last_captured_at = now
    row.last_snapshot_classification = decision.classification
    row.last_success_at = now
    row.failure_count = 0
    row.error_message = None
    row.lease_owner = None
    row.lease_expires_at = None
    if decision.classification == "DUPLICATE":
        row.duplicate_snapshot_count += 1
    elif decision.classification == "STALE":
        row.stale_snapshot_count += 1
    elif decision.classification == "AMBIGUOUS":
        row.ambiguous_snapshot_count += 1
        if (row.status == "final" or status == "final"):
            row.pending_final_correction_count += 1
    else:
        row.accepted_snapshot_count += 1
    if decision.accepted:
        row.status = status
        row.provider_as_of = ordering.provider_updated_at
        row.accepted_snapshot_hash = snapshot.snapshot_hash
        # Retain these legacy fields as accepted-state aliases for existing
        # consumers; rejected captures never overwrite canonical data.
        row.latest_snapshot_hash = snapshot.snapshot_hash
        row.latest_payload = summary
    interval = (
        FINAL_RECONCILIATION_INTERVAL_SECONDS
        if row.status == "final"
        else PRE_KICKOFF_POLL_INTERVAL_SECONDS
        if row.status == "scheduled"
        else MIN_GAME_POLL_INTERVAL_SECONDS
    )
    row.next_poll_at = now + timedelta(seconds=interval)
    db.commit()
    return decision


def record_espn_game_failure(
    db: Session,
    *,
    claim: ClaimedGame,
    error: Exception,
    now: datetime | None = None,
) -> ProviderGamePoll | None:
    now = _as_utc(now) or _utc_now()
    row = db.get(ProviderGamePoll, claim.id)
    if row is None:
        return None
    row.failure_count += 1
    status, retry_seconds = _failure_policy(error, failure_count=row.failure_count)
    row.status = status
    row.error_message = str(error)[:500]
    row.lease_owner = None
    row.lease_expires_at = None
    row.next_poll_at = now + timedelta(seconds=retry_seconds)
    db.commit()
    return row


def _assert_complete_espn_summary(
    db: Session,
    *,
    claim: ClaimedGame,
    summary: dict[str, Any],
    normalized_rows: list[dict[str, Any]],
) -> None:
    """Reject empty or regressive snapshots before they can replace scores."""

    # A game summary with no player rows is not a valid zero-score response.
    # Treat it as degraded provider data and preserve the prior canonical rows.
    if not extract_player_box_score_stats(summary):
        raise ProviderDataIncompleteError("ESPN summary contains no player box-score rows")
    row = db.get(ProviderGamePoll, claim.id)
    previous_snapshot = _accepted_snapshot(db, row) if row is not None else None
    previous_ids = {
        int(item["player_id"])
        for item in (previous_snapshot.normalized_rows or [])
        if isinstance(item, dict) and item.get("player_id") is not None
    } if previous_snapshot else set()
    current_ids = {int(item["player_id"]) for item in normalized_rows}
    if previous_ids and not previous_ids.issubset(current_ids):
        raise ProviderDataIncompleteError("ESPN summary is missing a previously verified player row")


def run_espn_scoring_cycle(
    db: Session,
    *,
    season: int,
    week: int,
    mode: LiveScoringMode,
    client: ESPNClient,
    worker_id: str | None = None,
    now: datetime | None = None,
    relevant_team_names: set[str] | None = None,
) -> EspnCycleResult:
    """Run one safe provider cycle.  HTTP is always outside the DB lease transaction."""

    if mode not in {"shadow", "enabled"}:
        raise ValueError("ESPN scoring mode must be shadow or enabled")
    current = _as_utc(now) or _utc_now()
    discovered = 0
    if discovery_due(db, season=season, week=week, now=current):
        try:
            events = client.get_scoreboard_events(season=season, week=week)
            discovered = discover_relevant_espn_games(
                db,
                season=season,
                week=week,
                events=events,
                relevant_team_names=relevant_team_names if relevant_team_names is not None else rostered_school_keys(db, season=season),
                now=current,
            )
            record_discovery_attempt(db, season=season, week=week, now=current, success=True)
            db.commit()
        except Exception as error:
            record_discovery_attempt(db, season=season, week=week, now=current, success=False, error=error)
            db.commit()
            return EspnCycleResult(0, 0, 0, 1, 0, 0, 0)

    claims = claim_due_espn_games(db, season=season, week=week, worker_id=worker_id, now=current)
    successful = failed = normalized_count = unmatched_count = promoted = 0
    pending_promotion: list[dict[str, Any]] = []
    corrected_provider_game_ids: set[str] = set()
    for claim in claims:
        try:
            response_metadata: dict[str, str] = {}
            get_summary_response = getattr(client, "get_summary_response", None)
            if callable(get_summary_response):
                response = get_summary_response(claim.provider_game_id)
                if isinstance(response, ESPNProviderResponse):
                    summary = response.payload
                    response_metadata = response.response_metadata
                else:
                    # Third-party test doubles may expose an equivalent
                    # response shape without importing our dataclass.
                    summary = getattr(response, "payload", None)
                    response_metadata = dict(getattr(response, "response_metadata", {}) or {})
                    if not isinstance(summary, dict):
                        raise TypeError("ESPN summary response payload must be an object")
            else:
                summary = client.get_summary(claim.provider_game_id)
            normalized, unmatched = normalize_espn_summary_player_stats(
                db,
                season=season,
                week=week,
                summary=summary,
                strict_identity=True,
            )
            _assert_complete_espn_summary(
                db,
                claim=claim,
                summary=summary,
                normalized_rows=normalized,
            )
            poll = db.get(ProviderGamePoll, claim.id)
            previous_snapshot = _accepted_snapshot(db, poll) if poll is not None else None
            decision = record_espn_game_success(
                db,
                claim=claim,
                summary=summary,
                normalized_rows=normalized,
                response_metadata=response_metadata,
                now=current,
            )
            if decision.verified_final_correction:
                corrected_provider_game_ids.add(claim.provider_game_id)
            if decision.accepted:
                pending_promotion.extend(normalized)
                if mode == "enabled":
                    # This consumes the same accepted, persisted provider
                    # snapshot as scoring. It makes no provider request. Keep
                    # shadow mode observational-only: it must not surface new
                    # public matchup state before the existing readiness gate
                    # has approved live scoring.
                    from collegefootballfantasy_api.app.services.live_projection import (
                        persist_live_projections_for_snapshot,
                    )

                    accepted = _accepted_snapshot(db, db.get(ProviderGamePoll, claim.id))
                    if accepted is not None:
                        queue_accepted_espn_long_play_notifications(
                            db,
                            provider_game_id=claim.provider_game_id,
                            summary=summary,
                            previous_snapshot=previous_snapshot,
                        )
                        persist_live_projections_for_snapshot(db, snapshot=accepted)
                        db.commit()
            successful += 1
            normalized_count += len(normalized)
            unmatched_count += unmatched
        except Exception as error:
            record_espn_game_failure(db, claim=claim, error=error, now=current)
            failed += 1

    if mode == "enabled" and pending_promotion:
        # Promotion is intentionally a short database operation after every
        # provider request has completed.  Shadow mode stops before this line.
        # The gate lives at the authority boundary, not only in process
        # configuration: a worker may start correctly then encounter an
        # unresolved starter or an unhealthy provider before a later cycle.
        from collegefootballfantasy_api.app.services.live_scoring_readiness import assert_public_scoring_ready

        assert_public_scoring_ready(db, season=season, week=week, now=current)
        promoted = persist_normalized_espn_player_stats(
            db,
            season=season,
            week=week,
            normalized_rows=pending_promotion,
        )
        db.commit()
        # Existing scoring is the sole public-score authority.  It reads the
        # newly promoted canonical totals and transactionally updates every
        # affected league from the same shared provider cache.
        from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation

        run_league_scoring_recalculation(
            db,
            league_id=None,
            season=season,
            week=week,
            provider=ESPN_PROVIDER,
        )
        certify_espn_matchup_finality(
            db,
            season=season,
            week=week,
            corrected_provider_game_ids=corrected_provider_game_ids,
        )
        # Future outlook snapshots are intentionally downstream of certified
        # fantasy-week finality.  A live, stale, or partial provider payload
        # may update the current matchup but can never rewrite Week N+1.
        from collegefootballfantasy_api.app.services.weekly_outlook_refresh import refresh_post_final_outlook

        refresh_post_final_outlook(db, season=season, completed_week=week)
        db.commit()

    return EspnCycleResult(
        discovered_games=discovered,
        claimed_games=len(claims),
        successful_games=successful,
        failed_games=failed,
        normalized_rows=normalized_count,
        unmatched_rows=unmatched_count,
        promoted_rows=promoted,
    )
