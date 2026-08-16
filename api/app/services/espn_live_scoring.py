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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import ESPNClient, extract_player_box_score_stats
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll, ProviderGameSnapshot
from collegefootballfantasy_api.app.models.roster import RosterEntry
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


class ProviderDataIncompleteError(RuntimeError):
    """An ESPN response cannot safely replace the last verified game totals."""


@dataclass(frozen=True)
class ClaimedGame:
    id: int
    provider_game_id: str
    season: int
    week: int


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
            # scoreboard discovery must not accidentally clear that safety state.
            if row.status != "blocked":
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
            ProviderGamePoll.status.in_(("scheduled", "live", "final", "delayed")),
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
    now: datetime,
) -> str:
    snapshot_hash = _canonical_hash(summary)
    snapshot = ProviderGameSnapshot(
        provider=ESPN_PROVIDER,
        provider_game_id=row.provider_game_id,
        season=row.season,
        week=row.week,
        status=status,
        provider_as_of=now,
        snapshot_hash=snapshot_hash,
        raw_payload=summary,
        normalized_rows=normalized_rows,
    )
    try:
        with db.begin_nested():
            db.add(snapshot)
            db.flush()
    except IntegrityError:
        # Identical replay: preserve the existing immutable audit snapshot.
        pass
    row.latest_snapshot_hash = snapshot_hash
    row.latest_payload = summary
    return snapshot_hash


def record_espn_game_success(
    db: Session,
    *,
    claim: ClaimedGame,
    summary: dict[str, Any],
    normalized_rows: list[dict[str, Any]],
    now: datetime | None = None,
) -> ProviderGamePoll:
    now = _as_utc(now) or _utc_now()
    row = db.get(ProviderGamePoll, claim.id)
    if row is None or row.provider != ESPN_PROVIDER or row.provider_game_id != claim.provider_game_id:
        raise LookupError("claimed ESPN game no longer exists")
    status = _summary_status(summary, row.status)
    _store_snapshot(db, row=row, summary=summary, normalized_rows=normalized_rows, status=status, now=now)
    row.status = status
    row.provider_as_of = now
    row.last_success_at = now
    row.failure_count = 0
    row.error_message = None
    row.lease_owner = None
    row.lease_expires_at = None
    interval = (
        FINAL_RECONCILIATION_INTERVAL_SECONDS
        if status == "final"
        else PRE_KICKOFF_POLL_INTERVAL_SECONDS
        if status == "scheduled"
        else MIN_GAME_POLL_INTERVAL_SECONDS
    )
    row.next_poll_at = now + timedelta(seconds=interval)
    db.commit()
    return row


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
    previous_snapshot = (
        db.query(ProviderGameSnapshot)
        .filter(
            ProviderGameSnapshot.provider == ESPN_PROVIDER,
            ProviderGameSnapshot.provider_game_id == claim.provider_game_id,
        )
        .order_by(ProviderGameSnapshot.id.desc())
        .first()
    )
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
            summary = client.get_summary(claim.provider_game_id)
            poll_before_update = db.get(ProviderGamePoll, claim.id)
            previous_snapshot_hash = poll_before_update.latest_snapshot_hash if poll_before_update is not None else None
            snapshot_hash = _canonical_hash(summary)
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
            record_espn_game_success(
                db,
                claim=claim,
                summary=summary,
                normalized_rows=normalized,
                now=current,
            )
            if previous_snapshot_hash and previous_snapshot_hash != snapshot_hash:
                corrected_provider_game_ids.add(claim.provider_game_id)
            pending_promotion.extend(normalized)
            successful += 1
            normalized_count += len(normalized)
            unmatched_count += unmatched
        except Exception as error:
            record_espn_game_failure(db, claim=claim, error=error, now=current)
            failed += 1

    if mode == "enabled" and pending_promotion:
        # Promotion is intentionally a short database operation after every
        # provider request has completed.  Shadow mode stops before this line.
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

    return EspnCycleResult(
        discovered_games=discovered,
        claimed_games=len(claims),
        successful_games=successful,
        failed_games=failed,
        normalized_rows=normalized_count,
        unmatched_rows=unmatched_count,
        promoted_rows=promoted,
    )
