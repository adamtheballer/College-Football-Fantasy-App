"""Safe synchronization of canonical team kickoff times.

``TeamSchedule`` is the only schedule authority exposed to player cards,
rosters, matchup rows, locks, and Pick 6.  Provider ``Game`` rows mirror that
authority; synchronizing only them is therefore intentionally insufficient.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
from collegefootballfantasy_api.app.models.schedule_sync_issue import ScheduleSyncIssue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school
from collegefootballfantasy_api.app.services.provider_identity import audit_identity_event
from collegefootballfantasy_api.app.services.provider_cache import get_or_create_sync_state, scope_dict_to_key


logger = logging.getLogger(__name__)
ScheduleSource = Literal["espn", "sportsdata"]
_FINAL_STATUSES = {"final", "post", "completed"}


@dataclass(frozen=True)
class ProviderScheduleGame:
    external_game_id: str
    season: int
    week: int
    home_team: str
    away_team: str
    kickoff_at: datetime | None
    status: str = "scheduled"
    venue: str | None = None
    network: str | None = None
    source_updated_at: datetime | None = None


@dataclass
class ScheduleSyncSummary:
    season: int
    week: int
    source: str
    games_fetched: int = 0
    games_matched: int = 0
    games_updated: int = 0
    tbd_games_unchanged: int = 0
    games_still_missing_time: int = 0
    skipped_manual_override: int = 0
    skipped_low_confidence: int = 0
    skipped_completed: int = 0
    errors: list[str] = field(default_factory=list)
    issues: dict[str, int] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def finish(self) -> "ScheduleSyncSummary":
        self.completed_at = datetime.now(timezone.utc)
        return self

    def as_dict(self) -> dict:
        return asdict(self)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def team_key(value: str | None) -> str:
    """Canonicalize supported aliases, then safely normalize any opponent."""

    canonical = canonical_school_name(value or "")
    if canonical:
        return normalize_school(canonical)
    ascii_value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return normalize_school(ascii_value)


def _provider_status(event: dict) -> str:
    status = event.get("status") if isinstance(event.get("status"), dict) else {}
    status_type = status.get("type") if isinstance(status.get("type"), dict) else {}
    state = str(status_type.get("state") or status_type.get("name") or "scheduled").strip().lower()
    return "final" if state in {"post", "final", "completed"} else "live" if state in {"in", "live"} else "scheduled"


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc(parsed)


def _espn_events(*, season: int, week: int) -> list[ProviderScheduleGame]:
    observed_at = datetime.now(timezone.utc)
    with ESPNClient() as client:
        raw_events = client.get_scoreboard_events(season=season, week=week)
    result: list[ProviderScheduleGame] = []
    for event in raw_events:
        event_id = str(event.get("id") or "").strip()
        competition = next((value for value in event.get("competitions", []) if isinstance(value, dict)), None)
        if not event_id or competition is None:
            continue
        competitors = competition.get("competitors")
        if not isinstance(competitors, list):
            continue
        home = next((row for row in competitors if isinstance(row, dict) and row.get("homeAway") == "home"), None)
        away = next((row for row in competitors if isinstance(row, dict) and row.get("homeAway") == "away"), None)
        home_team = ((home or {}).get("team") or {}).get("displayName") if isinstance((home or {}).get("team"), dict) else None
        away_team = ((away or {}).get("team") or {}).get("displayName") if isinstance((away or {}).get("team"), dict) else None
        if not isinstance(home_team, str) or not isinstance(away_team, str):
            continue
        broadcasts = competition.get("broadcasts")
        broadcast = next((item for item in broadcasts if isinstance(item, dict)), {}) if isinstance(broadcasts, list) else {}
        names = broadcast.get("names") if isinstance(broadcast, dict) else None
        venue_payload = competition.get("venue") if isinstance(competition.get("venue"), dict) else {}
        result.append(ProviderScheduleGame(
            external_game_id=event_id,
            season=season,
            week=week,
            home_team=home_team,
            away_team=away_team,
            kickoff_at=_parse_datetime(competition.get("date") or event.get("date")),
            status=_provider_status(event),
            venue=str(venue_payload.get("fullName")).strip() if venue_payload.get("fullName") else None,
            network=str(names[0]).strip() if isinstance(names, list) and names and names[0] else None,
            source_updated_at=observed_at,
        ))
    return result


def _sportsdata_events(*, season: int, week: int) -> list[ProviderScheduleGame]:
    observed_at = datetime.now(timezone.utc)
    result: list[ProviderScheduleGame] = []
    for row in SportsDataClient().get_schedule(season=season):
        try:
            row_week = int(row.get("Week") if row.get("Week") is not None else row.get("GameWeek"))
        except (TypeError, ValueError):
            continue
        if row_week != week:
            continue
        home = str(row.get("HomeTeamName") or row.get("HomeTeam") or "").strip()
        away = str(row.get("AwayTeamName") or row.get("AwayTeam") or "").strip()
        event_id = str(row.get("GameID") or row.get("GameId") or row.get("GlobalGameID") or "").strip()
        if not home or not away or not event_id:
            continue
        result.append(ProviderScheduleGame(
            external_game_id=event_id,
            season=season,
            week=week,
            home_team=home,
            away_team=away,
            kickoff_at=_parse_datetime(row.get("DateTime") or row.get("Day") or row.get("Date")),
            status=str(row.get("Status") or row.get("GameStatus") or "scheduled").strip().lower(),
            venue=str(row.get("Stadium") or row.get("Venue") or "").strip() or None,
            network=str(row.get("Channel") or row.get("Network") or "").strip() or None,
            source_updated_at=observed_at,
        ))
    return result


def fetch_schedule_events(*, source: ScheduleSource, season: int, week: int) -> list[ProviderScheduleGame]:
    if source == "sportsdata":
        return _sportsdata_events(season=season, week=week)
    return _espn_events(season=season, week=week)


def _issue(
    db: Session,
    summary: ScheduleSyncSummary,
    *,
    row: TeamSchedule,
    issue_type: str,
    current_value: str | None,
    provider_value: str | None,
    confidence: float | None,
    notes: str | None,
) -> None:
    existing = db.scalar(select(ScheduleSyncIssue).where(
        ScheduleSyncIssue.season == row.season,
        ScheduleSyncIssue.week == row.week,
        ScheduleSyncIssue.team_name == row.team_name,
        ScheduleSyncIssue.opponent_name == row.opponent_name,
        ScheduleSyncIssue.issue_type == issue_type,
        ScheduleSyncIssue.source == summary.source,
        ScheduleSyncIssue.resolved_at.is_(None),
    ))
    if existing is None:
        existing = ScheduleSyncIssue(
            season=row.season, week=row.week, team_name=row.team_name, opponent_name=row.opponent_name,
            issue_type=issue_type, source=summary.source,
        )
        db.add(existing)
    existing.current_value = current_value
    existing.provider_value = provider_value
    existing.confidence = confidence
    existing.notes = notes
    summary.issues[issue_type] = summary.issues.get(issue_type, 0) + 1


def _resolve_issues_for_row(db: Session, *, row: TeamSchedule, source: str) -> None:
    for issue in db.scalars(select(ScheduleSyncIssue).where(
        ScheduleSyncIssue.season == row.season,
        ScheduleSyncIssue.week == row.week,
        ScheduleSyncIssue.team_name == row.team_name,
        ScheduleSyncIssue.opponent_name == row.opponent_name,
        ScheduleSyncIssue.source == source,
        ScheduleSyncIssue.resolved_at.is_(None),
    )):
        issue.resolved_at = datetime.now(timezone.utc)


def _same_participants(game: Game, event: ProviderScheduleGame) -> bool:
    return {team_key(game.home_team), team_key(game.away_team)} == {team_key(event.home_team), team_key(event.away_team)}


def _event_matches_schedule(event: ProviderScheduleGame, row: TeamSchedule) -> bool:
    if not row.opponent_name:
        return False
    return {team_key(row.team_name), team_key(row.opponent_name)} == {team_key(event.home_team), team_key(event.away_team)}


def _canonical_event_game(db: Session, *, row: TeamSchedule, event: ProviderScheduleGame) -> Game | None:
    linked = db.get(Game, row.game_id) if row.game_id else None
    provider_game = db.scalar(select(Game).where(Game.external_id == event.external_game_id))
    if linked is not None and not _same_participants(linked, event):
        return None
    if provider_game is not None and not _same_participants(provider_game, event):
        return None
    if provider_game is not None:
        return provider_game
    if linked is not None:
        return linked
    game = Game(
        external_id=event.external_game_id,
        season=event.season,
        week=event.week,
        home_team=event.home_team,
        away_team=event.away_team,
        start_date=event.kickoff_at,
        schedule_status=event.status,
    )
    db.add(game)
    db.flush()
    return game


def sync_schedule_times(
    db: Session,
    *,
    season: int,
    week: int,
    source: ScheduleSource = "espn",
    force_current_week: bool = False,
    provider_events: Iterable[ProviderScheduleGame] | None = None,
    now: datetime | None = None,
    actor_user_id: int | None = None,
) -> ScheduleSyncSummary:
    """Synchronize one canonical week without inventing or downgrading times.

    This function deliberately does not commit.  Its caller owns the atomic
    provider state/audit transaction and can roll back a provider failure.
    """

    current = _utc(now) or datetime.now(timezone.utc)
    summary = ScheduleSyncSummary(season=season, week=week, source=source, started_at=current)
    if not force_current_week and week != calendar_cfb_week(season, current):
        summary.errors.append("refusing non-current week without force_current_week")
        return summary.finish()

    events = list(provider_events) if provider_events is not None else fetch_schedule_events(source=source, season=season, week=week)
    events = [event for event in events if event.season == season and event.week == week]
    summary.games_fetched = len(events)
    schedule_rows = list(db.scalars(select(TeamSchedule).where(
        TeamSchedule.season == season,
        TeamSchedule.week == week,
        TeamSchedule.is_bye.is_(False),
    )))

    for row in schedule_rows:
        if row.manual_override:
            summary.skipped_manual_override += 1
            _issue(db, summary, row=row, issue_type="manual_override_skipped", current_value=row.kickoff_at.isoformat() if row.kickoff_at else None, provider_value=None, confidence=None, notes=row.manual_override_reason)
            continue
        candidates = [event for event in events if _event_matches_schedule(event, row)]
        if not candidates:
            _issue(db, summary, row=row, issue_type="game_not_found", current_value=row.kickoff_at.isoformat() if row.kickoff_at else None, provider_value=None, confidence=0.0, notes="No unique provider event matched the stored team/opponent pair.")
            continue
        if len(candidates) > 1:
            summary.skipped_low_confidence += 1
            _issue(db, summary, row=row, issue_type="duplicate_possible_match", current_value=row.kickoff_at.isoformat() if row.kickoff_at else None, provider_value=",".join(event.external_game_id for event in candidates), confidence=0.0, notes="Multiple provider events share the stored participant pair.")
            continue
        event = candidates[0]
        summary.games_matched += 1
        if event.kickoff_at is None:
            summary.games_still_missing_time += 1
            summary.tbd_games_unchanged += 1
            _issue(db, summary, row=row, issue_type="provider_missing_time", current_value=row.kickoff_at.isoformat() if row.kickoff_at else None, provider_value=None, confidence=1.0, notes="Provider verified the participants but did not publish a kickoff time.")
            continue
        linked_game = db.get(Game, row.game_id) if row.game_id else None
        if linked_game is not None and (linked_game.schedule_status or "").lower() in _FINAL_STATUSES and not force_current_week:
            summary.skipped_completed += 1
            continue
        game = _canonical_event_game(db, row=row, event=event)
        if game is None:
            summary.skipped_low_confidence += 1
            _issue(db, summary, row=row, issue_type="time_conflict", current_value=row.kickoff_at.isoformat() if row.kickoff_at else None, provider_value=event.kickoff_at.isoformat(), confidence=0.0, notes="A linked or provider Game has different participants; refusing to rewire automatically.")
            continue
        before = {
            "schedule_id": row.id, "game_id": row.game_id, "kickoff_at": row.kickoff_at.isoformat() if row.kickoff_at else None,
            "time_status": row.time_status, "schedule_source": row.schedule_source,
            "game_start_date": game.start_date.isoformat() if game.start_date else None,
            "external_game_id": game.external_id,
        }
        changed = _utc(row.kickoff_at) != event.kickoff_at or row.game_id != game.id or row.time_status != "confirmed"
        game.season, game.week = season, week
        game.home_team, game.away_team = event.home_team, event.away_team
        game.external_id = event.external_game_id
        game.start_date = event.kickoff_at
        if (game.schedule_status or "").lower() not in _FINAL_STATUSES:
            game.schedule_status = event.status
        row.game_id = game.id
        row.game_date = event.kickoff_at.date()
        row.kickoff_at = event.kickoff_at
        row.opponent_name = event.away_team if team_key(row.team_name) == team_key(event.home_team) else event.home_team
        row.location = "home" if team_key(row.team_name) == team_key(event.home_team) else "away"
        row.is_bye = False
        row.date_confirmed = True
        row.venue = event.venue or row.venue
        row.tv_network = event.network or row.tv_network
        row.time_status = "confirmed"
        row.schedule_source = source
        row.source_updated_at = event.source_updated_at or current
        row.last_synced_at = current
        row.schedule_confidence = 1.0
        row.source_url = "https://site.api.espn.com/" if source == "espn" else row.source_url
        if changed:
            summary.games_updated += 1
            audit_identity_event(
                db, entity_type="team_schedule", entity_id=row.id, action="sync_kickoff_time", provider=source,
                provider_team_id=event.external_game_id, before_state=before,
                actor_user_id=actor_user_id,
                after_state={"schedule_id": row.id, "game_id": game.id, "kickoff_at": event.kickoff_at.isoformat(), "time_status": "confirmed", "source": source, "confidence": 1.0},
                reason="Verified provider schedule synchronization; confirmed kickoff replaced only equal-or-weaker schedule state.",
            )
        _resolve_issues_for_row(db, row=row, source=source)

    db.flush()
    if summary.games_updated:
        # A changed kickoff can change lineup locks and first-kickoff notices.
        # Rebuild through the existing durable-notification path rather than
        # inventing a second scheduling implementation here.
        from collegefootballfantasy_api.app.services.notification_service import rebuild_matchup_start_notifications_for_schedule

        rebuild_matchup_start_notifications_for_schedule(db, season=season, weeks={week})
    logger.info("schedule_time_sync_complete %s", summary.as_dict())
    return summary.finish()


def resolve_schedule_sync_source() -> ScheduleSource:
    configured = settings.schedule_sync_source
    if configured == "auto":
        return "sportsdata" if settings.sportsdata_enabled and settings.sportsdata_api_key else "espn"
    return configured


def run_due_schedule_sync(
    db: Session,
    *,
    season: int | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """Run one guarded daily retry in the existing lifecycle worker.

    There is no separate Railway process to crash.  A persisted state key
    makes the 5-second lifecycle loop perform at most one fetch per local day
    while allowing Tuesday through Saturday retries for still-TBD games.
    """

    if not settings.schedule_sync_enabled:
        return {"status": "disabled"}
    current = _utc(now) or datetime.now(timezone.utc)
    from zoneinfo import ZoneInfo

    eastern = current.astimezone(ZoneInfo("America/New_York"))
    if eastern.weekday() not in {1, 2, 3, 4, 5} or eastern.hour < settings.schedule_sync_hour_et:
        return {"status": "not_due"}
    season_value = season or settings.current_season_year
    week = calendar_cfb_week(season_value, current)
    source = resolve_schedule_sync_source()
    scope = {"season": season_value, "week": week, "date_et": eastern.date().isoformat()}
    state = get_or_create_sync_state(db, source, "schedule_time_sync", scope_dict_to_key(scope))
    if state.status == "ready" and state.last_success_at is not None:
        return {"status": "already_completed", "season": season_value, "week": week, "source": source}
    if state.last_attempted_at is not None and (current - _utc(state.last_attempted_at)).total_seconds() < 1_800:
        # The lifecycle process wakes every five seconds.  A provider failure
        # must be visible and retryable, but never turn that loop into a
        # request storm.  Successful runs are handled by the daily guard
        # above; failed/in-flight runs share this explicit 30-minute backoff.
        status = "in_progress" if state.status == "syncing" else "retry_backoff"
        return {"status": status, "season": season_value, "week": week, "source": source}
    state.status = "syncing"
    state.last_attempted_at = current
    db.flush()
    try:
        summary = sync_schedule_times(
            db, season=season_value, week=week, source=source, force_current_week=True, now=current,
        )
        state.status = "ready"
        state.last_success_at = summary.completed_at
        state.error_message = None
        state.consecutive_failures = 0
        state.meta = summary.as_dict()
        db.flush()
        return {"status": "completed", **summary.as_dict()}
    except Exception as exc:
        state.status = "failed"
        state.error_message = str(exc)[:500]
        state.consecutive_failures = (state.consecutive_failures or 0) + 1
        db.flush()
        logger.exception("schedule_time_sync_failed season=%s week=%s source=%s", season_value, week, source)
        return {"status": "failed", "season": season_value, "week": week, "source": source, "error": str(exc)}


def apply_manual_kickoff_override(
    db: Session,
    *,
    schedule_id: int,
    kickoff_at: datetime,
    reason: str,
    actor_user_id: int,
) -> TeamSchedule:
    """Apply a reviewed manual time to every side of the same canonical game."""

    row = db.get(TeamSchedule, schedule_id)
    if row is None:
        raise LookupError("schedule row not found")
    if row.is_bye:
        raise ValueError("a bye week cannot have a kickoff time")
    kickoff = _utc(kickoff_at)
    if kickoff is None:
        raise ValueError("kickoff_at is required")
    linked_rows = [row]
    game = db.get(Game, row.game_id) if row.game_id else None
    if game is not None:
        linked_rows = list(db.scalars(select(TeamSchedule).where(TeamSchedule.game_id == game.id)))
        game.start_date = kickoff
    for target in linked_rows:
        before = {
            "kickoff_at": target.kickoff_at.isoformat() if target.kickoff_at else None,
            "time_status": target.time_status,
            "manual_override": target.manual_override,
        }
        target.kickoff_at = kickoff
        target.game_date = kickoff.date()
        target.date_confirmed = True
        target.time_status = "manual_override"
        target.schedule_source = "manual_override"
        target.source_updated_at = datetime.now(timezone.utc)
        target.last_synced_at = target.source_updated_at
        target.schedule_confidence = 1.0
        target.manual_override = True
        target.manual_override_reason = reason
        audit_identity_event(
            db, entity_type="team_schedule", entity_id=target.id, action="manual_kickoff_override",
            actor_user_id=actor_user_id, before_state=before,
            after_state={"kickoff_at": kickoff.isoformat(), "time_status": "manual_override", "reason": reason},
            reason="Administrator manually verified a kickoff time after schedule sync review.",
        )
        _resolve_issues_for_row(db, row=target, source="espn")
        _resolve_issues_for_row(db, row=target, source="sportsdata")
    from collegefootballfantasy_api.app.services.notification_service import rebuild_matchup_start_notifications_for_schedule

    rebuild_matchup_start_notifications_for_schedule(db, season=row.season, weeks={row.week})
    db.flush()
    return row
