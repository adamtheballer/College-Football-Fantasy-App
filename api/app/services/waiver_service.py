from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_waiver_availability import PlayerWaiverAvailability
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_claim_audit import WaiverClaimAudit
from collegefootballfantasy_api.app.models.waiver_period import WaiverPeriod
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.models.waiver_processing_run import WaiverProcessingRun
from collegefootballfantasy_api.app.schemas.waiver import FreeAgentAdd, FreeAgentAddRead, WaiverClaimCreate, WaiverClaimRead
from collegefootballfantasy_api.app.services.chat_service import create_system_chat_message
from collegefootballfantasy_api.app.services.league_weeks import current_cfb_week_state
from collegefootballfantasy_api.app.services.player_lock_service import is_player_locked
from collegefootballfantasy_api.app.services.roster_slots import first_open_eligible_slot

WAIVER_STATUS_PENDING = "pending"
WAIVER_STATUS_CANCELLED = "cancelled"
WAIVER_STATUS_WON = "won"
WAIVER_STATUS_LOST = "lost"
WAIVER_STATUS_INVALID = "invalid"
WAIVER_STATUS_INSUFFICIENT_BUDGET = "insufficient_budget"
WAIVER_STATUS_ROSTER_FULL = "roster_full"
WAIVER_STATUS_PLAYER_UNAVAILABLE = "player_unavailable"
WAIVER_STATUS_FAILED = "failed"

TERMINAL_WAIVER_STATUSES = {
    WAIVER_STATUS_CANCELLED,
    WAIVER_STATUS_WON,
    WAIVER_STATUS_LOST,
    WAIVER_STATUS_INVALID,
    WAIVER_STATUS_INSUFFICIENT_BUDGET,
    WAIVER_STATUS_ROSTER_FULL,
    WAIVER_STATUS_PLAYER_UNAVAILABLE,
    WAIVER_STATUS_FAILED,
}
DEFAULT_WAIVER_PERIOD_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _league_timezone_name(db: Session, league: League, settings: LeagueSettings | None = None) -> str:
    if settings and settings.waiver_timezone:
        return settings.waiver_timezone
    draft = db.query(Draft).filter(Draft.league_id == league.id).first()
    return draft.timezone if draft and draft.timezone else "America/New_York"


def _league_timezone(db: Session, league: League, settings: LeagueSettings | None = None) -> ZoneInfo:
    try:
        return ZoneInfo(_league_timezone_name(db, league, settings))
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/New_York")


def _league_settings(db: Session, league_id: int) -> LeagueSettings:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return settings


def _waiver_type(settings: LeagueSettings) -> str:
    waiver_type = (settings.waiver_type or "").strip().lower()
    if waiver_type not in {"faab", "priority"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="league waiver type is not supported")
    return waiver_type


def _waiver_period_hours(settings: LeagueSettings) -> int:
    value = settings.waiver_period_hours
    return max(1, min(int(value if value is not None else DEFAULT_WAIVER_PERIOD_HOURS), 168))


def _next_waiver_process_time(
    db: Session,
    league: League,
    settings: LeagueSettings,
    *,
    now: datetime | None = None,
) -> datetime:
    """Return the next future league-local processing timestamp in UTC."""

    current = _as_utc(now or _now())
    if settings.next_waiver_run_at is not None and _as_utc(settings.next_waiver_run_at) > current:
        return _as_utc(settings.next_waiver_run_at)
    local_now = current.astimezone(_league_timezone(db, league, settings))
    weekday_offset = (int(settings.waiver_processing_weekday) - local_now.weekday()) % 7
    candidate = (local_now + timedelta(days=weekday_offset)).replace(
        hour=int(settings.waiver_processing_hour), minute=0, second=0, microsecond=0
    )
    if candidate <= local_now:
        candidate += timedelta(days=7)
    settings.next_waiver_run_at = candidate.astimezone(timezone.utc)
    db.add(settings)
    return settings.next_waiver_run_at


def _owned_team(db: Session, league_id: int, user_id: int) -> Team:
    team = db.query(Team).filter(Team.league_id == league_id, Team.owner_user_id == user_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required")
    return team


def _serialize_claim(db: Session, claim: WaiverClaim) -> WaiverClaimRead:
    add_player = db.get(Player, claim.add_player_id)
    drop_player = db.get(Player, claim.drop_player_id) if claim.drop_player_id else None
    return WaiverClaimRead(
        id=claim.id,
        league_id=claim.league_id,
        team_id=claim.team_id,
        fantasy_team_id=claim.team_id,
        add_player_id=claim.add_player_id,
        add_player_name=add_player.name if add_player else "Unknown Player",
        drop_roster_entry_id=claim.drop_roster_entry_id,
        drop_player_id=claim.drop_player_id,
        drop_player_name=drop_player.name if drop_player else None,
        priority=claim.priority_snapshot,
        faab_bid=claim.faab_bid,
        status=claim.status,
        failure_reason=claim.failure_reason,
        failure_code=claim.failure_code,
        season=claim.season,
        processing_week=claim.processing_week,
        processing_window_id=claim.processing_window_id,
        waiver_period_id=claim.waiver_period_id,
        processing_run_id=claim.processing_run_id,
        preference_order=claim.preference_order,
        winning_bid=claim.winning_bid,
        prior_priority=claim.prior_priority,
        resulting_priority=claim.resulting_priority,
        process_after=claim.process_after,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
        processed_at=claim.processed_at,
    )


def serialize_claims(db: Session, claims: list[WaiverClaim]) -> list[WaiverClaimRead]:
    return [_serialize_claim(db, claim) for claim in claims]


def _claim_state(claim: WaiverClaim) -> dict:
    return {
        "id": claim.id,
        "league_id": claim.league_id,
        "team_id": claim.team_id,
        "add_player_id": claim.add_player_id,
        "drop_roster_entry_id": claim.drop_roster_entry_id,
        "drop_player_id": claim.drop_player_id,
        "waiver_period_id": claim.waiver_period_id,
        "preference_order": claim.preference_order,
        "status": claim.status,
        "priority_snapshot": claim.priority_snapshot,
        "faab_bid": claim.faab_bid,
        "process_after": claim.process_after.isoformat() if claim.process_after else None,
        "failure_code": claim.failure_code,
        "failure_reason": claim.failure_reason,
        "processed_at": claim.processed_at.isoformat() if claim.processed_at else None,
    }


def _audit_claim(
    db: Session,
    claim: WaiverClaim,
    *,
    action: str,
    actor_user_id: int | None,
    reason: str | None = None,
    before_state: dict | None = None,
) -> None:
    db.add(
        WaiverClaimAudit(
            waiver_claim_id=claim.id,
            league_id=claim.league_id,
            team_id=claim.team_id,
            action=action,
            actor_user_id=actor_user_id,
            reason=reason,
            before_state=before_state,
            after_state=_claim_state(claim),
        )
    )


def _notify_user(
    db: Session,
    *,
    user_id: int | None,
    alert_type: str,
    title: str,
    body: str,
    payload: dict,
) -> None:
    if user_id is None:
        return
    db.add(
        NotificationLog(
            user_id=user_id,
            user_key=str(user_id),
            alert_type=alert_type,
            title=title,
            body=body,
            payload=payload,
        )
    )


def _official_draft_or_error(db: Session, league_id: int) -> Draft:
    draft = db.query(Draft).filter(Draft.league_id == league_id).first()
    if not draft or draft.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="waivers are unavailable until the official draft is completed",
        )
    return draft


def _official_draft_team_order(db: Session, draft: Draft) -> list[int]:
    first_pick_by_team: dict[int, int] = {}
    for pick in (
        db.query(DraftPick)
        .filter(DraftPick.draft_id == draft.id)
        .order_by(DraftPick.overall_pick.asc(), DraftPick.id.asc())
        .all()
    ):
        first_pick_by_team.setdefault(pick.team_id, pick.overall_pick)
    if not first_pick_by_team:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="official draft has no finalized draft order")
    return [team_id for team_id, _ in sorted(first_pick_by_team.items(), key=lambda item: (item[1], item[0]))]


def _priority_rows(db: Session, league_id: int, *, for_update: bool = False) -> list[WaiverPriority]:
    query = db.query(WaiverPriority).filter(WaiverPriority.league_id == league_id).order_by(
        WaiverPriority.priority.asc(), WaiverPriority.team_id.asc()
    )
    return query.with_for_update().all() if for_update else query.all()


def _set_priority_order(db: Session, league_id: int, ordered_team_ids: list[int]) -> dict[int, WaiverPriority]:
    """Resequence with a temporary offset so unique priority constraints stay valid."""

    rows = _priority_rows(db, league_id, for_update=True)
    rows_by_team = {row.team_id: row for row in rows}
    if set(rows_by_team) != set(ordered_team_ids) or len(ordered_team_ids) != len(set(ordered_team_ids)):
        raise RuntimeError("waiver priority team set is inconsistent")
    offset = len(rows) + max((row.priority for row in rows), default=0) + 1
    for row in rows:
        row.priority += offset
    db.flush()
    for priority, team_id in enumerate(ordered_team_ids, start=1):
        rows_by_team[team_id].priority = priority
    db.flush()
    return rows_by_team


def initialize_waiver_state_after_official_draft(
    db: Session,
    league: League,
    *,
    now: datetime | None = None,
) -> dict[int, WaiverPriority]:
    """Initialize FAAB balances and the shared tie-break order only after the official draft."""

    settings = _league_settings(db, league.id)
    _waiver_type(settings)
    draft = _official_draft_or_error(db, league.id)
    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.id.asc()).all()
    draft_order = _official_draft_team_order(db, draft)
    active_team_ids = [team.id for team in teams]
    if set(draft_order) != set(active_team_ids):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="official draft order does not match league teams")

    existing = _priority_rows(db, league.id, for_update=True)
    if settings.waiver_initialized_at:
        if {row.team_id for row in existing} != set(active_team_ids):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="waiver priority state is incomplete")
        return {row.team_id: row for row in existing}

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="waiver priorities exist before official initialization")
    for priority, team_id in enumerate(reversed(draft_order), start=1):
        db.add(
            WaiverPriority(
                league_id=league.id,
                team_id=team_id,
                priority=priority,
                faab_budget=int(settings.faab_starting_budget),
                faab_spent=0,
            )
        )
    settings.waiver_initialized_at = _as_utc(now or _now())
    db.add(settings)
    db.flush()
    return {row.team_id: row for row in _priority_rows(db, league.id, for_update=True)}


def _remaining_faab(priority: WaiverPriority) -> int:
    return priority.faab_remaining


def _get_or_create_period(
    db: Session,
    *,
    league: League,
    settings: LeagueSettings,
    now: datetime,
) -> WaiverPeriod:
    scheduled_for = _next_waiver_process_time(db, league, settings, now=now)
    week_state = current_cfb_week_state(
        league.season_year,
        now=scheduled_for,
        timezone_name=_league_timezone_name(db, league, settings),
    )
    window_key = f"{league.season_year}-week-{week_state.week}-tuesday-{scheduled_for.strftime('%Y%m%dT%H%M%SZ')}"
    period = (
        db.query(WaiverPeriod)
        .filter(
            WaiverPeriod.league_id == league.id,
            WaiverPeriod.season == league.season_year,
            WaiverPeriod.week == week_state.week,
            WaiverPeriod.window_key == window_key,
        )
        .first()
    )
    if period:
        return period
    period = WaiverPeriod(
        league_id=league.id,
        season=league.season_year,
        week=week_state.week,
        window_key=window_key,
        opens_at=now,
        closes_at=scheduled_for,
        processes_at=scheduled_for,
        status="open",
    )
    db.add(period)
    db.flush()
    return period


def _ensure_player_available(db: Session, league_id: int, player_id: int, *, now: datetime) -> None:
    rostered = (
        db.query(RosterEntry.id)
        .filter(RosterEntry.league_id == league_id, RosterEntry.player_id == player_id)
        .first()
    )
    if rostered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster")
    availability = (
        db.query(PlayerWaiverAvailability)
        .filter(
            PlayerWaiverAvailability.league_id == league_id,
            PlayerWaiverAvailability.player_id == player_id,
        )
        .first()
    )
    if not availability:
        return
    if availability.state in {"rostered", "game_locked"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is not currently available on waivers")
    if availability.available_at and _as_utc(availability.available_at) > now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is not currently available on waivers")


def _has_completed_waiver_period(db: Session, league_id: int) -> bool:
    return (
        db.query(WaiverPeriod.id)
        .filter(WaiverPeriod.league_id == league_id, WaiverPeriod.status == "completed")
        .first()
        is not None
    )


def _ensure_player_is_free_agent(
    db: Session,
    league_id: int,
    player_id: int,
    *,
    now: datetime,
) -> None:
    rostered = (
        db.query(RosterEntry.id)
        .filter(RosterEntry.league_id == league_id, RosterEntry.player_id == player_id)
        .first()
    )
    if rostered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster")

    availability = _availability_row(db, league_id, player_id, for_update=True)
    if availability is None:
        if not _has_completed_waiver_period(db, league_id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is currently available on waivers")
        return
    if availability.state in {"rostered", "game_locked", "claim_pending"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is not currently a free agent")
    if availability.state in {"waiver_locked", "waivers"}:
        if availability.available_at is None or _as_utc(availability.available_at) > now:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is currently available on waivers")
        availability.state = "free_agent"
        availability.available_at = None
        availability.waiver_period_id = None
        db.add(availability)
        return
    if availability.state != "free_agent":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is not currently a free agent")


def _validate_no_kicked_off_players(
    db: Session,
    league: League,
    player_ids: set[int],
    *,
    now: datetime | None = None,
) -> None:
    if not player_ids:
        return
    players = db.query(Player).filter(Player.id.in_(player_ids)).all()
    school_names = {player.school for player in players if player.school}
    if not school_names:
        return
    current = _as_utc(now or _now())
    settings = _league_settings(db, league.id)
    week_state = current_cfb_week_state(league.season_year, now=current, timezone_name=_league_timezone_name(db, league, settings))
    games = (
        db.query(Game)
        .filter(Game.season == league.season_year, Game.week == week_state.week, Game.start_date.isnot(None))
        .filter(or_(Game.home_team.in_(school_names), Game.away_team.in_(school_names)))
        .all()
    )
    locked_schools = {
        school
        for game in games
        if game.start_date is not None and _as_utc(game.start_date) <= current
        for school in (game.home_team, game.away_team)
        if school in school_names
    }
    if locked_schools:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"waiver moves are locked after kickoff for: {', '.join(sorted(locked_schools))}",
        )


def _validate_drop_player_unlocked(db: Session, league: League, player_id: int | None, *, now: datetime) -> None:
    if player_id is None:
        return
    settings = _league_settings(db, league.id)
    week_state = current_cfb_week_state(league.season_year, now=now, timezone_name=_league_timezone_name(db, league, settings))
    if is_player_locked(db, player_id=player_id, season=league.season_year, week=week_state.week, now=now):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="locked drop player cannot be waived")


def _drop_entry_for_payload(db: Session, team: Team, drop_roster_entry_id: int | None) -> RosterEntry | None:
    if drop_roster_entry_id is None:
        return None
    entry = db.get(RosterEntry, drop_roster_entry_id)
    if not entry or entry.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")
    return entry


def _validate_payload_team(payload: WaiverClaimCreate, team: Team) -> None:
    requested_team_id = payload.team_id or payload.fantasy_team_id
    if requested_team_id is not None and requested_team_id != team.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="waiver claim team does not match owned team")


def _best_slot_after_drop(
    db: Session,
    team: Team,
    add_player: Player,
    roster_slots: dict,
    drop_entry: RosterEntry | None,
    *,
    superflex_enabled: bool,
) -> tuple[str, int]:
    roster_entries = db.query(RosterEntry).filter(RosterEntry.team_id == team.id).all()
    if drop_entry is not None:
        roster_entries = [entry for entry in roster_entries if entry.id != drop_entry.id]
    slot = first_open_eligible_slot(
        team.id,
        add_player.position,
        roster_slots,
        roster_entries,
        superflex_enabled=superflex_enabled,
    )
    if slot is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="team roster is full")
    return slot


def _next_preference_order(db: Session, team_id: int, waiver_period_id: int) -> int:
    pending = (
        db.query(WaiverClaim)
        .filter(
            WaiverClaim.team_id == team_id,
            WaiverClaim.waiver_period_id == waiver_period_id,
            WaiverClaim.status == WAIVER_STATUS_PENDING,
        )
        .all()
    )
    return max((claim.preference_order for claim in pending), default=0) + 1


def submit_waiver_claim(
    db: Session,
    *,
    league: League,
    current_user: User,
    payload: WaiverClaimCreate,
) -> WaiverClaimRead:
    now = _now()
    settings = _league_settings(db, league.id)
    if not settings.waivers_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="waivers are currently paused")
    _waiver_type(settings)
    team = _owned_team(db, league.id, current_user.id)
    _validate_payload_team(payload, team)
    priorities = initialize_waiver_state_after_official_draft(db, league, now=now)
    period = _get_or_create_period(db, league=league, settings=settings, now=now)
    if period.status not in {"scheduled", "open"} or _as_utc(period.closes_at) <= now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="waiver claim window is closed")
    add_player = db.get(Player, payload.add_player_id)
    if not add_player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    _ensure_player_available(db, league.id, add_player.id, now=now)
    drop_entry = _drop_entry_for_payload(db, team, payload.drop_roster_entry_id)
    _validate_no_kicked_off_players(db, league, {add_player.id, drop_entry.player_id if drop_entry else 0} - {0}, now=now)
    _best_slot_after_drop(
        db,
        team,
        add_player,
        settings.roster_slots_json or {},
        drop_entry,
        superflex_enabled=bool(settings.superflex_enabled),
    )
    priority = priorities[team.id]
    waiver_type = _waiver_type(settings)
    if waiver_type == "faab" and not settings.allow_zero_faab_bids and payload.faab_bid == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="zero-dollar FAAB bids are disabled")
    if waiver_type == "faab" and payload.faab_bid > _remaining_faab(priority):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient FAAB budget")
    if (
        db.query(WaiverClaim.id)
        .filter(
            WaiverClaim.team_id == team.id,
            WaiverClaim.waiver_period_id == period.id,
            WaiverClaim.add_player_id == add_player.id,
            WaiverClaim.status == WAIVER_STATUS_PENDING,
        )
        .first()
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate pending waiver claim")

    preference_order = payload.preference_order or _next_preference_order(db, team.id, period.id)
    claim = WaiverClaim(
        league_id=league.id,
        team_id=team.id,
        add_player_id=add_player.id,
        drop_roster_entry_id=drop_entry.id if drop_entry else None,
        drop_player_id=drop_entry.player_id if drop_entry else None,
        created_by_user_id=current_user.id,
        status=WAIVER_STATUS_PENDING,
        season=period.season,
        processing_week=period.week,
        processing_window_id=period.window_key,
        waiver_period_id=period.id,
        preference_order=preference_order,
        priority_snapshot=priority.priority,
        faab_bid=payload.faab_bid if waiver_type == "faab" else 0,
        process_after=period.processes_at,
    )
    db.add(claim)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="claim preference or player is already pending") from exc
    _audit_claim(db, claim, action="submitted", actor_user_id=current_user.id, reason=payload.reason)
    _notify_user(
        db,
        user_id=current_user.id,
        alert_type="WAIVER_SUBMITTED",
        title="Waiver claim submitted",
        body=f"Claim submitted for {add_player.name}.",
        payload={"league_id": league.id, "claim_id": claim.id, "add_player_id": add_player.id},
    )
    db.commit()
    db.refresh(claim)
    return _serialize_claim(db, claim)


def add_free_agent(
    db: Session,
    *,
    league: League,
    current_user: User,
    player_id: int,
    payload: FreeAgentAdd,
) -> FreeAgentAddRead:
    """Immediately add a league free agent without a waiver claim or FAAB charge."""

    now = _now()
    settings = _league_settings(db, league.id)
    if not settings.waivers_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="waivers are currently paused")
    team = _owned_team(db, league.id, current_user.id)
    requested_team_id = payload.team_id or payload.fantasy_team_id
    if requested_team_id is not None and requested_team_id != team.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="free-agent team does not match owned team")
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    _ensure_player_is_free_agent(db, league.id, player.id, now=now)
    drop_entry = _drop_entry_for_payload(db, team, payload.drop_roster_entry_id)
    _validate_no_kicked_off_players(db, league, {player.id, drop_entry.player_id if drop_entry else 0} - {0}, now=now)
    _validate_drop_player_unlocked(db, league, drop_entry.player_id if drop_entry else None, now=now)
    slot, slot_index = _best_slot_after_drop(
        db,
        team,
        player,
        settings.roster_slots_json or {},
        drop_entry,
        superflex_enabled=bool(settings.superflex_enabled),
    )

    dropped_player_id = drop_entry.player_id if drop_entry else None
    if drop_entry is not None:
        db.delete(drop_entry)
        db.flush()
    roster_entry = RosterEntry(
        league_id=league.id,
        team_id=team.id,
        player_id=player.id,
        slot=slot,
        slot_index=slot_index,
        status="active",
    )
    db.add(roster_entry)
    transaction = Transaction(
        league_id=league.id,
        team_id=team.id,
        transaction_type="free_agent_add_drop" if dropped_player_id else "free_agent_add",
        player_id=player.id,
        related_player_id=dropped_player_id,
        created_by_user_id=current_user.id,
        reason="free-agent add",
    )
    db.add(transaction)
    db.flush()
    _mark_player_rostered(db, league.id, player.id)
    if dropped_player_id is not None:
        _mark_player_dropped(
            db,
            league=league,
            settings=settings,
            player_id=dropped_player_id,
            team_id=team.id,
            transaction_id=transaction.id,
            period_id=None,
            now=now,
        )
    _notify_user(
        db,
        user_id=team.owner_user_id,
        alert_type="FREE_AGENT_ADDED",
        title="Free agent added",
        body=f"You added {player.name}." if dropped_player_id is None else f"You added {player.name} and dropped a player.",
        payload={"league_id": league.id, "transaction_id": transaction.id, "player_id": player.id},
    )
    create_system_chat_message(
        db,
        league_id=league.id,
        message_type="waiver",
        body=(
            f"{team.name} added free agent {player.name}."
            if dropped_player_id is None
            else f"{team.name} added free agent {player.name} and made a roster drop."
        ),
        metadata_json={"transaction_id": transaction.id, "team_id": team.id, "player_id": player.id},
        event_key=f"free-agent-add:{transaction.id}",
    )
    db.commit()
    db.refresh(roster_entry)
    return FreeAgentAddRead(
        team_id=team.id,
        player_id=player.id,
        player_name=player.name,
        roster_entry_id=roster_entry.id,
        slot=slot,
        slot_index=slot_index,
        transaction_id=transaction.id,
    )


def _assert_claim_editable(claim: WaiverClaim, now: datetime) -> None:
    if claim.status != WAIVER_STATUS_PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only pending waiver claims can be changed")
    if claim.process_after and _as_utc(claim.process_after) <= now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="waiver claim window is closed")


def cancel_waiver_claim(
    db: Session,
    *,
    league: League,
    current_user: User,
    claim_id: int,
    reason: str | None = None,
) -> WaiverClaimRead:
    team = _owned_team(db, league.id, current_user.id)
    claim = db.get(WaiverClaim, claim_id)
    if not claim or claim.league_id != league.id or claim.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="waiver claim not found")
    _assert_claim_editable(claim, _now())
    before = _claim_state(claim)
    claim.status = WAIVER_STATUS_CANCELLED
    claim.processed_at = _now()
    db.add(claim)
    _audit_claim(db, claim, action="cancelled", actor_user_id=current_user.id, reason=reason, before_state=before)
    _notify_user(
        db,
        user_id=current_user.id,
        alert_type="WAIVER_CANCELLED",
        title="Waiver claim cancelled",
        body="Your pending waiver claim was cancelled.",
        payload={"league_id": league.id, "claim_id": claim.id},
    )
    db.commit()
    db.refresh(claim)
    return _serialize_claim(db, claim)


def edit_waiver_claim(
    db: Session,
    *,
    league: League,
    current_user: User,
    claim_id: int,
    payload: WaiverClaimCreate,
) -> WaiverClaimRead:
    team = _owned_team(db, league.id, current_user.id)
    claim = db.get(WaiverClaim, claim_id)
    if not claim or claim.league_id != league.id or claim.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="waiver claim not found")
    now = _now()
    _assert_claim_editable(claim, now)
    settings = _league_settings(db, league.id)
    _validate_payload_team(payload, team)
    add_player = db.get(Player, payload.add_player_id)
    if not add_player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    _ensure_player_available(db, league.id, add_player.id, now=now)
    drop_entry = _drop_entry_for_payload(db, team, payload.drop_roster_entry_id)
    _best_slot_after_drop(
        db, team, add_player, settings.roster_slots_json or {}, drop_entry, superflex_enabled=bool(settings.superflex_enabled)
    )
    priority = db.query(WaiverPriority).filter(WaiverPriority.team_id == team.id).with_for_update().one()
    if _waiver_type(settings) == "faab" and payload.faab_bid > _remaining_faab(priority):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient FAAB budget")
    before = _claim_state(claim)
    claim.add_player_id = add_player.id
    claim.drop_roster_entry_id = drop_entry.id if drop_entry else None
    claim.drop_player_id = drop_entry.player_id if drop_entry else None
    claim.faab_bid = payload.faab_bid if _waiver_type(settings) == "faab" else 0
    db.add(claim)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate pending waiver claim") from exc
    _audit_claim(db, claim, action="edited", actor_user_id=current_user.id, reason=payload.reason, before_state=before)
    db.commit()
    db.refresh(claim)
    return _serialize_claim(db, claim)


def reorder_waiver_claims(
    db: Session,
    *,
    league: League,
    current_user: User,
    claim_ids: list[int],
) -> list[WaiverClaimRead]:
    team = _owned_team(db, league.id, current_user.id)
    claims = (
        db.query(WaiverClaim)
        .filter(WaiverClaim.team_id == team.id, WaiverClaim.status == WAIVER_STATUS_PENDING)
        .order_by(WaiverClaim.preference_order.asc(), WaiverClaim.id.asc())
        .with_for_update()
        .all()
    )
    if not claims:
        return []
    period_ids = {claim.waiver_period_id for claim in claims}
    if len(period_ids) != 1 or set(claim_ids) != {claim.id for claim in claims} or len(claim_ids) != len(set(claim_ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="claim reorder must include every pending claim in one waiver period")
    current = _now()
    for claim in claims:
        _assert_claim_editable(claim, current)
    offset = len(claims) + max(claim.preference_order for claim in claims) + 1
    for claim in claims:
        claim.preference_order += offset
    db.flush()
    by_id = {claim.id: claim for claim in claims}
    for preference_order, claim_id in enumerate(claim_ids, start=1):
        claim = by_id[claim_id]
        before = _claim_state(claim)
        claim.preference_order = preference_order
        _audit_claim(db, claim, action="reordered", actor_user_id=current_user.id, before_state=before)
    db.commit()
    return serialize_claims(db, [by_id[claim_id] for claim_id in claim_ids])


def _move_team_to_bottom(db: Session, league_id: int, winning_team_id: int) -> tuple[int, int]:
    priorities = _priority_rows(db, league_id, for_update=True)
    prior_order = [row.team_id for row in priorities]
    if winning_team_id not in prior_order:
        raise RuntimeError("winning team has no waiver priority")
    prior_priority = prior_order.index(winning_team_id) + 1
    new_order = [team_id for team_id in prior_order if team_id != winning_team_id] + [winning_team_id]
    _set_priority_order(db, league_id, new_order)
    return prior_priority, len(new_order)


def _claim_failure(claim: WaiverClaim, *, status_value: str, code: str, reason: str, now: datetime) -> None:
    claim.status = status_value
    claim.failure_code = code
    claim.failure_reason = reason
    claim.processed_at = now


def _load_drop_entry(db: Session, claim: WaiverClaim, team: Team) -> RosterEntry | None:
    if claim.drop_roster_entry_id is not None:
        entry = db.get(RosterEntry, claim.drop_roster_entry_id)
        if not entry or entry.league_id != claim.league_id or entry.team_id != team.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="drop roster entry no longer on roster")
        if claim.drop_player_id is not None and entry.player_id != claim.drop_player_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="drop roster entry player changed")
        return entry
    if claim.drop_player_id is not None:
        entry = (
            db.query(RosterEntry)
            .filter(
                RosterEntry.league_id == claim.league_id,
                RosterEntry.team_id == team.id,
                RosterEntry.player_id == claim.drop_player_id,
            )
            .first()
        )
        if not entry:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="drop player no longer on roster")
        return entry
    return None


def _validate_claim_for_processing(
    db: Session,
    *,
    league: League,
    settings: LeagueSettings,
    claim: WaiverClaim,
    priority: WaiverPriority,
    now: datetime,
) -> tuple[Team, Player, RosterEntry | None, tuple[str, int]]:
    team = db.get(Team, claim.team_id)
    add_player = db.get(Player, claim.add_player_id)
    if not team or team.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="claim team no longer exists")
    if not add_player:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="claim player no longer exists")
    _ensure_player_available(db, league.id, claim.add_player_id, now=now)
    drop_entry = _load_drop_entry(db, claim, team)
    _validate_no_kicked_off_players(db, league, {claim.add_player_id, drop_entry.player_id if drop_entry else 0} - {0}, now=now)
    if _waiver_type(settings) == "faab" and claim.faab_bid > _remaining_faab(priority):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient FAAB budget")
    _validate_drop_player_unlocked(db, league, drop_entry.player_id if drop_entry else None, now=now)
    slot = _best_slot_after_drop(
        db, team, add_player, settings.roster_slots_json or {}, drop_entry, superflex_enabled=bool(settings.superflex_enabled)
    )
    return team, add_player, drop_entry, slot


def _availability_row(db: Session, league_id: int, player_id: int, *, for_update: bool = False) -> PlayerWaiverAvailability | None:
    query = db.query(PlayerWaiverAvailability).filter(
        PlayerWaiverAvailability.league_id == league_id,
        PlayerWaiverAvailability.player_id == player_id,
    )
    return query.with_for_update().one_or_none() if for_update else query.one_or_none()


def _mark_player_rostered(db: Session, league_id: int, player_id: int) -> None:
    availability = _availability_row(db, league_id, player_id, for_update=True)
    if availability is None:
        availability = PlayerWaiverAvailability(league_id=league_id, player_id=player_id)
        db.add(availability)
    availability.state = "rostered"
    availability.available_at = None
    availability.waiver_period_id = None


def _mark_player_dropped(
    db: Session,
    *,
    league: League,
    settings: LeagueSettings,
    player_id: int,
    team_id: int,
    transaction_id: int | None,
    period_id: int | None,
    now: datetime,
) -> None:
    availability = _availability_row(db, league.id, player_id, for_update=True)
    unlock_at = now + timedelta(hours=int(settings.post_drop_waiver_hours))
    if not availability:
        availability = PlayerWaiverAvailability(league_id=league.id, player_id=player_id)
        db.add(availability)
    availability.state = "waiver_locked"
    availability.available_at = unlock_at
    availability.waiver_period_id = period_id
    availability.source_transaction_id = transaction_id
    availability.dropped_by_team_id = team_id


def record_player_dropped_for_waivers(
    db: Session,
    *,
    league: League,
    player_id: int,
    team_id: int,
    transaction_id: int | None,
    now: datetime | None = None,
) -> None:
    """Place a directly dropped player into the league's waiver hold.

    Roster and waiver mutations intentionally share this one lifecycle update so
    a normal roster drop cannot bypass the post-drop waiver rule.
    """

    settings = _league_settings(db, league.id)
    _mark_player_dropped(
        db,
        league=league,
        settings=settings,
        player_id=player_id,
        team_id=team_id,
        transaction_id=transaction_id,
        period_id=None,
        now=_as_utc(now or _now()),
    )


def record_player_rostered_for_waivers(db: Session, *, league_id: int, player_id: int) -> None:
    """Mark a directly added player as rostered in the league availability map."""

    _mark_player_rostered(db, league_id, player_id)


def _apply_claim_award(
    db: Session,
    *,
    league: League,
    settings: LeagueSettings,
    claim: WaiverClaim,
    priority: WaiverPriority,
    run: WaiverProcessingRun,
    now: datetime,
    move_priority: bool,
) -> None:
    team, add_player, drop_entry, (new_slot, new_slot_index) = _validate_claim_for_processing(
        db, league=league, settings=settings, claim=claim, priority=priority, now=now
    )
    before = _claim_state(claim)
    dropped_player_id = drop_entry.player_id if drop_entry else None
    if drop_entry:
        db.delete(drop_entry)
        db.flush()
    db.add(
        RosterEntry(
            league_id=league.id,
            team_id=team.id,
            player_id=claim.add_player_id,
            slot=new_slot,
            slot_index=new_slot_index,
            status="active",
        )
    )
    transaction = Transaction(
        league_id=league.id,
        team_id=team.id,
        transaction_type="waiver_add_drop" if dropped_player_id else "waiver_add",
        player_id=claim.add_player_id,
        related_player_id=dropped_player_id,
        created_by_user_id=claim.created_by_user_id,
        reason=f"waiver claim #{claim.id}",
    )
    db.add(transaction)
    db.flush()
    if _waiver_type(settings) == "faab":
        priority.faab_spent += int(claim.faab_bid or 0)
        claim.winning_bid = int(claim.faab_bid or 0)
    if move_priority:
        claim.prior_priority, claim.resulting_priority = _move_team_to_bottom(db, league.id, team.id)
    claim.status = WAIVER_STATUS_WON
    claim.failure_code = None
    claim.failure_reason = None
    claim.processing_run_id = run.id
    claim.processed_at = now
    db.add(claim)
    _mark_player_rostered(db, league.id, add_player.id)
    if dropped_player_id:
        _mark_player_dropped(
            db,
            league=league,
            settings=settings,
            player_id=dropped_player_id,
            team_id=team.id,
            transaction_id=transaction.id,
            period_id=claim.waiver_period_id,
            now=now,
        )
    _audit_claim(db, claim, action="won", actor_user_id=None, before_state=before)
    _notify_user(
        db,
        user_id=team.owner_user_id,
        alert_type="WAIVER_PROCESSED",
        title="Waiver claim successful",
        body=(
            f"You added {add_player.name} for ${claim.winning_bid} FAAB."
            if _waiver_type(settings) == "faab"
            else f"You added {add_player.name} and moved to the back of waiver priority."
        ),
        payload={"league_id": league.id, "claim_id": claim.id, "run_id": run.id},
    )
    chat_body = (
        f"{team.name} claimed {add_player.name} for ${claim.winning_bid} FAAB."
        if _waiver_type(settings) == "faab"
        else f"{team.name} claimed {add_player.name} and moved to waiver priority #{claim.resulting_priority}."
    )
    create_system_chat_message(
        db,
        league_id=league.id,
        message_type="waiver",
        body=chat_body,
        metadata_json={"claim_id": claim.id, "run_id": run.id, "team_id": team.id, "player_id": add_player.id},
        event_key=f"waiver-award:{claim.id}",
    )


def _terminalize_claim(
    db: Session,
    claim: WaiverClaim,
    *,
    status_value: str,
    code: str,
    reason: str,
    now: datetime,
    run: WaiverProcessingRun,
) -> None:
    if claim.status != WAIVER_STATUS_PENDING:
        return
    before = _claim_state(claim)
    _claim_failure(claim, status_value=status_value, code=code, reason=reason, now=now)
    claim.processing_run_id = run.id
    db.add(claim)
    _audit_claim(db, claim, action=status_value, actor_user_id=None, reason=reason, before_state=before)
    team = db.get(Team, claim.team_id)
    _notify_user(
        db,
        user_id=team.owner_user_id if team else claim.created_by_user_id,
        alert_type="WAIVER_FAILED" if status_value != WAIVER_STATUS_LOST else "WAIVER_LOST",
        title="Waiver claim unsuccessful",
        body=reason,
        payload={"league_id": claim.league_id, "claim_id": claim.id, "run_id": run.id},
    )


def _classify_processing_exception(exc: HTTPException) -> tuple[str, str]:
    detail = str(exc.detail)
    if "budget" in detail:
        return WAIVER_STATUS_INSUFFICIENT_BUDGET, "insufficient_budget"
    if "roster is full" in detail:
        return WAIVER_STATUS_ROSTER_FULL, "roster_full"
    if "already on a league roster" in detail or "not currently available" in detail or "locked after kickoff" in detail:
        return WAIVER_STATUS_PLAYER_UNAVAILABLE, "player_unavailable"
    return WAIVER_STATUS_INVALID, "invalid_claim"


def _faab_group_sort_key(claims: list[WaiverClaim]) -> tuple:
    lead = min(claims, key=lambda claim: (claim.preference_order, claim.created_at or _now(), claim.id))
    return (lead.preference_order, lead.created_at or _now(), lead.add_player_id)


def _process_faab_period(
    db: Session,
    *,
    league: League,
    settings: LeagueSettings,
    period: WaiverPeriod,
    run: WaiverProcessingRun,
    now: datetime,
) -> tuple[int, int]:
    claims = (
        db.query(WaiverClaim)
        .filter(WaiverClaim.waiver_period_id == period.id, WaiverClaim.status == WAIVER_STATUS_PENDING)
        .order_by(WaiverClaim.preference_order.asc(), WaiverClaim.created_at.asc(), WaiverClaim.id.asc())
        .with_for_update()
        .all()
    )
    by_player: dict[int, list[WaiverClaim]] = defaultdict(list)
    for claim in claims:
        by_player[claim.add_player_id].append(claim)
    processed = 0
    failures = 0
    for target_claims in sorted(by_player.values(), key=_faab_group_sort_key):
        priorities = {row.team_id: row for row in _priority_rows(db, league.id, for_update=True)}
        valid: list[WaiverClaim] = []
        for claim in target_claims:
            priority = priorities.get(claim.team_id)
            if not priority:
                _terminalize_claim(db, claim, status_value=WAIVER_STATUS_INVALID, code="missing_priority", reason="waiver priority is missing", now=now, run=run)
                failures += 1
                continue
            try:
                _validate_claim_for_processing(db, league=league, settings=settings, claim=claim, priority=priority, now=now)
            except HTTPException as exc:
                status_value, code = _classify_processing_exception(exc)
                _terminalize_claim(db, claim, status_value=status_value, code=code, reason=str(exc.detail), now=now, run=run)
                failures += 1
                continue
            valid.append(claim)
        if not valid:
            continue
        valid.sort(
            key=lambda claim: (
                -int(claim.faab_bid or 0),
                priorities[claim.team_id].priority,
                claim.created_at or now,
                claim.id,
            )
        )
        winner = valid[0]
        highest_bid = int(winner.faab_bid or 0)
        tied = sum(1 for claim in valid if int(claim.faab_bid or 0) == highest_bid) > 1
        try:
            _apply_claim_award(
                db,
                league=league,
                settings=settings,
                claim=winner,
                priority=priorities[winner.team_id],
                run=run,
                now=now,
                move_priority=tied and settings.waiver_tiebreaker == "priority",
            )
            processed += 1
        except HTTPException as exc:
            status_value, code = _classify_processing_exception(exc)
            _terminalize_claim(db, winner, status_value=status_value, code=code, reason=str(exc.detail), now=now, run=run)
            failures += 1
            continue
        for claim in valid[1:]:
            _terminalize_claim(
                db,
                claim,
                status_value=WAIVER_STATUS_LOST,
                code="outbid_or_tiebreak",
                reason="another manager won this waiver claim",
                now=now,
                run=run,
            )
            processed += 1
    return processed, failures


def _process_priority_period(
    db: Session,
    *,
    league: League,
    settings: LeagueSettings,
    period: WaiverPeriod,
    run: WaiverProcessingRun,
    now: datetime,
) -> tuple[int, int]:
    processed = 0
    failures = 0
    while True:
        pending = (
            db.query(WaiverClaim)
            .filter(WaiverClaim.waiver_period_id == period.id, WaiverClaim.status == WAIVER_STATUS_PENDING)
            .order_by(WaiverClaim.preference_order.asc(), WaiverClaim.created_at.asc(), WaiverClaim.id.asc())
            .with_for_update()
            .all()
        )
        if not pending:
            break
        priority_rows = _priority_rows(db, league.id, for_update=True)
        claim_by_team: dict[int, list[WaiverClaim]] = defaultdict(list)
        for claim in pending:
            claim_by_team[claim.team_id].append(claim)
        made_progress = False
        for priority in priority_rows:
            team_claims = claim_by_team.get(priority.team_id, [])
            if not team_claims:
                continue
            candidate = team_claims[0]
            try:
                _validate_claim_for_processing(
                    db, league=league, settings=settings, claim=candidate, priority=priority, now=now
                )
            except HTTPException as exc:
                status_value, code = _classify_processing_exception(exc)
                _terminalize_claim(db, candidate, status_value=status_value, code=code, reason=str(exc.detail), now=now, run=run)
                failures += 1
                made_progress = True
                break
            try:
                _apply_claim_award(
                    db,
                    league=league,
                    settings=settings,
                    claim=candidate,
                    priority=priority,
                    run=run,
                    now=now,
                    move_priority=True,
                )
            except HTTPException as exc:
                status_value, code = _classify_processing_exception(exc)
                _terminalize_claim(db, candidate, status_value=status_value, code=code, reason=str(exc.detail), now=now, run=run)
                failures += 1
                made_progress = True
                break
            for competitor in pending:
                if competitor.id != candidate.id and competitor.add_player_id == candidate.add_player_id:
                    _terminalize_claim(
                        db,
                        competitor,
                        status_value=WAIVER_STATUS_LOST,
                        code="priority_lost",
                        reason="a higher-priority manager won this waiver claim",
                        now=now,
                        run=run,
                    )
                    processed += 1
            processed += 1
            made_progress = True
            break  # reload the live priority order after every mutation.
        if not made_progress:
            break
    return processed, failures


def _release_expired_availability(db: Session, *, league_id: int, now: datetime) -> None:
    rows = (
        db.query(PlayerWaiverAvailability)
        .filter(
            PlayerWaiverAvailability.league_id == league_id,
            PlayerWaiverAvailability.state.in_(("waiver_locked", "waivers")),
            PlayerWaiverAvailability.available_at.isnot(None),
            PlayerWaiverAvailability.available_at <= now,
        )
        .with_for_update()
        .all()
    )
    for row in rows:
        row.state = "free_agent"
        row.waiver_period_id = None


def _process_period(db: Session, *, league: League, period: WaiverPeriod, now: datetime) -> tuple[int, int]:
    settings = _league_settings(db, league.id)
    if not settings.waivers_enabled:
        return 0, 0
    initialize_waiver_state_after_official_draft(db, league, now=now)
    period = db.query(WaiverPeriod).filter(WaiverPeriod.id == period.id).with_for_update().one()
    existing_run = (
        db.query(WaiverProcessingRun).filter(WaiverProcessingRun.waiver_period_id == period.id).with_for_update().one_or_none()
    )
    if existing_run and existing_run.status == "completed":
        return 0, 0
    if period.status == "completed":
        return 0, 0
    if existing_run and existing_run.status == "running":
        return 0, 0
    if existing_run is None:
        run = WaiverProcessingRun(
            league_id=league.id,
            waiver_period_id=period.id,
            season=period.season,
            week=period.week,
            window_key=period.window_key,
            waiver_type=_waiver_type(settings),
            scheduled_for=period.processes_at,
            status="running",
            started_at=now,
            idempotency_key=f"waiver-period:{period.id}",
        )
        db.add(run)
        db.flush()
    else:
        run = existing_run
        run.status = "running"
        run.started_at = now
        run.error = None
    period.status = "processing"
    if _waiver_type(settings) == "faab":
        processed, failures = _process_faab_period(db, league=league, settings=settings, period=period, run=run, now=now)
    else:
        processed, failures = _process_priority_period(db, league=league, settings=settings, period=period, run=run, now=now)
    _release_expired_availability(db, league_id=league.id, now=now)
    run.claims_processed = processed + failures
    run.claims_won = db.query(WaiverClaim).filter(WaiverClaim.processing_run_id == run.id, WaiverClaim.status == WAIVER_STATUS_WON).count()
    run.failure_count = failures
    run.status = "completed"
    run.completed_at = now
    period.status = "completed"
    period.processed_at = now
    settings.next_waiver_run_at = None
    _next_waiver_process_time(db, league, settings, now=now)
    return processed, failures


def process_waiver_claims_once(
    db: Session,
    *,
    league_id: int | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    processed_at = _as_utc(now or _now())
    query = db.query(WaiverPeriod).filter(
        WaiverPeriod.status.in_(("scheduled", "open", "failed")), WaiverPeriod.processes_at <= processed_at
    )
    if league_id is not None:
        query = query.filter(WaiverPeriod.league_id == league_id)
    periods = query.order_by(WaiverPeriod.processes_at.asc(), WaiverPeriod.id.asc()).with_for_update(skip_locked=True).all()
    summary = {"processed": 0, "failed": 0, "pending": 0}
    for period in periods:
        league = db.get(League, period.league_id)
        if not league:
            continue
        try:
            processed, failures = _process_period(db, league=league, period=period, now=processed_at)
            summary["processed"] += processed
            summary["failed"] += failures
            db.commit()
        except Exception as exc:  # Persist a failed ledger state after rolling back the partial run.
            db.rollback()
            failed_period = db.get(WaiverPeriod, period.id)
            if failed_period:
                failed_period.status = "failed"
            existing = db.query(WaiverProcessingRun).filter(WaiverProcessingRun.waiver_period_id == period.id).one_or_none()
            if existing:
                existing.status = "failed"
                existing.error = str(exc)[:2000]
            db.commit()
            summary["failed"] += 1
    remaining_query = db.query(WaiverClaim).filter(WaiverClaim.status == WAIVER_STATUS_PENDING)
    if league_id is not None:
        remaining_query = remaining_query.filter(WaiverClaim.league_id == league_id)
    summary["pending"] = remaining_query.count()
    return summary
