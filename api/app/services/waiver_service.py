from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_claim_audit import WaiverClaimAudit
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.schemas.waiver import WaiverClaimCreate, WaiverClaimRead
from collegefootballfantasy_api.app.services.roster_legality import assign_best_roster_slot_for_position

WAIVER_STATUS_PENDING = "pending"
WAIVER_STATUS_CANCELLED = "cancelled"
WAIVER_STATUS_PROCESSED = "processed"
WAIVER_STATUS_FAILED = "failed"
TERMINAL_WAIVER_STATUSES = {WAIVER_STATUS_CANCELLED, WAIVER_STATUS_PROCESSED, WAIVER_STATUS_FAILED}
DEFAULT_FAAB_BUDGET = 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _league_timezone(db: Session, league: League) -> ZoneInfo:
    draft = db.query(Draft).filter(Draft.league_id == league.id).first()
    timezone_name = draft.timezone if draft and draft.timezone else "America/New_York"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/New_York")


def _league_settings(db: Session, league_id: int) -> LeagueSettings:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return settings


def _waiver_type(settings: LeagueSettings) -> str:
    return (settings.waiver_type or "faab").strip().lower()


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
        fantasy_team_id=claim.team_id,
        add_player_id=claim.add_player_id,
        add_player_name=add_player.name if add_player else "Unknown Player",
        drop_player_id=claim.drop_player_id,
        drop_player_name=drop_player.name if drop_player else None,
        priority=claim.priority_snapshot,
        faab_bid=claim.faab_bid,
        status=claim.status,
        failure_reason=claim.failure_reason,
        created_at=claim.created_at,
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
        "drop_player_id": claim.drop_player_id,
        "status": claim.status,
        "priority_snapshot": claim.priority_snapshot,
        "faab_bid": claim.faab_bid,
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


def _ensure_priorities_for_league(db: Session, league_id: int) -> dict[int, WaiverPriority]:
    teams = db.query(Team).filter(Team.league_id == league_id).order_by(Team.id.asc()).all()
    existing = {
        row.team_id: row
        for row in db.query(WaiverPriority).filter(WaiverPriority.league_id == league_id).all()
    }
    next_priority = (max((row.priority for row in existing.values()), default=0) or 0) + 1
    for team in teams:
        if team.id in existing:
            continue
        row = WaiverPriority(
            league_id=league_id,
            team_id=team.id,
            priority=next_priority,
            faab_budget=DEFAULT_FAAB_BUDGET,
            faab_spent=0,
        )
        db.add(row)
        db.flush()
        existing[team.id] = row
        next_priority += 1
    return existing


def _remaining_faab(priority: WaiverPriority) -> int:
    return max(0, int(priority.faab_budget or 0) - int(priority.faab_spent or 0))


def _ensure_player_available(db: Session, league_id: int, player_id: int) -> None:
    existing = (
        db.query(RosterEntry.id)
        .filter(RosterEntry.league_id == league_id, RosterEntry.player_id == player_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster")


def _validate_no_gameday_for_players(
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
    league_tz = _league_timezone(db, league)
    league_date = _as_utc(now or _now()).astimezone(league_tz).date()
    games = (
        db.query(Game)
        .filter(Game.season == league.season_year, Game.start_date.isnot(None))
        .filter(or_(Game.home_team.in_(school_names), Game.away_team.in_(school_names)))
        .all()
    )
    gameday_schools: set[str] = set()
    for game in games:
        game_date = _as_utc(game.start_date).astimezone(league_tz).date()
        if game_date != league_date:
            continue
        if game.home_team in school_names:
            gameday_schools.add(game.home_team)
        if game.away_team in school_names:
            gameday_schools.add(game.away_team)
    if gameday_schools:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"waiver moves are blocked on gameday for: {', '.join(sorted(gameday_schools))}",
        )


def _drop_entry_for_payload(db: Session, team: Team, drop_roster_entry_id: int | None) -> RosterEntry | None:
    if drop_roster_entry_id is None:
        return None
    entry = db.get(RosterEntry, drop_roster_entry_id)
    if not entry or entry.team_id != team.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")
    return entry


def _best_slot_after_drop(
    db: Session,
    team: Team,
    add_player: Player,
    roster_slots: dict,
    drop_entry: RosterEntry | None,
    *,
    superflex_enabled: bool,
) -> str:
    roster_entries = db.query(RosterEntry).filter(RosterEntry.team_id == team.id).all()
    if drop_entry is not None:
        roster_entries = [entry for entry in roster_entries if entry.id != drop_entry.id]
    slot = assign_best_roster_slot_for_position(
        add_player.position,
        roster_entries,
        roster_slots,
        superflex_enabled=superflex_enabled,
    )
    if slot is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="team roster is full")
    return slot


def submit_waiver_claim(
    db: Session,
    *,
    league: League,
    current_user: User,
    payload: WaiverClaimCreate,
) -> WaiverClaimRead:
    settings = _league_settings(db, league.id)
    team = _owned_team(db, league.id, current_user.id)
    add_player = db.get(Player, payload.add_player_id)
    if not add_player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    _ensure_player_available(db, league.id, add_player.id)
    drop_entry = _drop_entry_for_payload(db, team, payload.drop_roster_entry_id)
    _validate_no_gameday_for_players(
        db,
        league,
        {add_player.id, drop_entry.player_id if drop_entry else 0} - {0},
    )
    _best_slot_after_drop(
        db,
        team,
        add_player,
        settings.roster_slots_json or {},
        drop_entry,
        superflex_enabled=bool(settings.superflex_enabled),
    )

    existing = (
        db.query(WaiverClaim)
        .filter(
            WaiverClaim.league_id == league.id,
            WaiverClaim.team_id == team.id,
            WaiverClaim.add_player_id == add_player.id,
            WaiverClaim.drop_player_id == (drop_entry.player_id if drop_entry else None),
            WaiverClaim.status == WAIVER_STATUS_PENDING,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate pending waiver claim")

    priorities = _ensure_priorities_for_league(db, league.id)
    priority = priorities[team.id]
    if _waiver_type(settings) == "faab" and payload.faab_bid > _remaining_faab(priority):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient FAAB budget")

    claim = WaiverClaim(
        league_id=league.id,
        team_id=team.id,
        add_player_id=add_player.id,
        drop_player_id=drop_entry.player_id if drop_entry else None,
        created_by_user_id=current_user.id,
        status=WAIVER_STATUS_PENDING,
        priority_snapshot=priority.priority,
        faab_bid=payload.faab_bid if _waiver_type(settings) == "faab" else 0,
    )
    db.add(claim)
    db.flush()
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
    if claim.status != WAIVER_STATUS_PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="only pending waiver claims can be cancelled")
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


def _move_team_to_bottom(db: Session, league_id: int, winning_team_id: int) -> None:
    priorities = (
        db.query(WaiverPriority)
        .filter(WaiverPriority.league_id == league_id)
        .order_by(WaiverPriority.priority.asc(), WaiverPriority.team_id.asc())
        .all()
    )
    winner = next((row for row in priorities if row.team_id == winning_team_id), None)
    if not winner:
        return
    old_priority = winner.priority
    max_priority = max(row.priority for row in priorities)
    for row in priorities:
        if row.team_id != winning_team_id and row.priority > old_priority:
            row.priority -= 1
    winner.priority = max_priority


def _pending_claim_sort_key(settings: LeagueSettings, priority_by_team: dict[int, WaiverPriority]):
    waiver_type = _waiver_type(settings)

    def key(claim: WaiverClaim) -> tuple:
        priority = priority_by_team.get(claim.team_id)
        priority_value = claim.priority_snapshot or (priority.priority if priority else 999_999)
        created_at = claim.created_at or _now()
        if waiver_type == "faab":
            return (-int(claim.faab_bid or 0), priority_value, created_at, claim.id)
        return (priority_value, created_at, claim.id)

    return key


def _process_single_claim(
    db: Session,
    *,
    league: League,
    settings: LeagueSettings,
    claim: WaiverClaim,
    priority: WaiverPriority,
    now: datetime,
) -> bool:
    before = _claim_state(claim)
    try:
        team = db.get(Team, claim.team_id)
        add_player = db.get(Player, claim.add_player_id)
        if not team or team.league_id != league.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="claim team no longer exists")
        if not add_player:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="claim player no longer exists")
        _ensure_player_available(db, league.id, claim.add_player_id)
        drop_entry = None
        if claim.drop_player_id is not None:
            drop_entry = (
                db.query(RosterEntry)
                .filter(
                    RosterEntry.league_id == league.id,
                    RosterEntry.team_id == team.id,
                    RosterEntry.player_id == claim.drop_player_id,
                )
                .first()
            )
            if not drop_entry:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="drop player no longer on roster")
        _validate_no_gameday_for_players(
            db,
            league,
            {claim.add_player_id, claim.drop_player_id or 0} - {0},
            now=now,
        )
        if _waiver_type(settings) == "faab" and claim.faab_bid > _remaining_faab(priority):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient FAAB budget")
        new_slot = _best_slot_after_drop(
            db,
            team,
            add_player,
            settings.roster_slots_json or {},
            drop_entry,
            superflex_enabled=bool(settings.superflex_enabled),
        )
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
                status="active",
            )
        )
        db.add(
            Transaction(
                league_id=league.id,
                team_id=team.id,
                transaction_type="waiver_add_drop" if dropped_player_id else "waiver_add",
                player_id=claim.add_player_id,
                related_player_id=dropped_player_id,
                created_by_user_id=claim.created_by_user_id,
                reason=f"waiver claim #{claim.id}",
            )
        )
        if _waiver_type(settings) == "faab":
            priority.faab_spent += int(claim.faab_bid or 0)
        else:
            _move_team_to_bottom(db, league.id, team.id)
        claim.status = WAIVER_STATUS_PROCESSED
        claim.processed_at = now
        db.add(claim)
        _audit_claim(db, claim, action="processed", actor_user_id=None, before_state=before)
        _notify_user(
            db,
            user_id=team.owner_user_id,
            alert_type="WAIVER_PROCESSED",
            title="Waiver claim processed",
            body=f"{add_player.name} was added to your roster.",
            payload={"league_id": league.id, "claim_id": claim.id, "add_player_id": claim.add_player_id},
        )
        return True
    except HTTPException as exc:
        claim.status = WAIVER_STATUS_FAILED
        claim.failure_reason = str(exc.detail)
        claim.processed_at = now
        db.add(claim)
        _audit_claim(db, claim, action="failed", actor_user_id=None, reason=claim.failure_reason, before_state=before)
        team = db.get(Team, claim.team_id)
        _notify_user(
            db,
            user_id=team.owner_user_id if team else claim.created_by_user_id,
            alert_type="WAIVER_FAILED",
            title="Waiver claim failed",
            body=claim.failure_reason or "The waiver claim could not be processed.",
            payload={"league_id": league.id, "claim_id": claim.id},
        )
        return False


def process_waiver_claims_once(
    db: Session,
    *,
    league_id: int | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    processed_at = _as_utc(now or _now())
    league_query = db.query(League)
    if league_id is not None:
        league_query = league_query.filter(League.id == league_id)
    leagues = league_query.order_by(League.id.asc()).all()
    summary = {"processed": 0, "failed": 0, "pending": 0}
    for league in leagues:
        pending = (
            db.query(WaiverClaim)
            .filter(WaiverClaim.league_id == league.id, WaiverClaim.status == WAIVER_STATUS_PENDING)
            .all()
        )
        if not pending:
            continue
        settings = _league_settings(db, league.id)
        priorities = _ensure_priorities_for_league(db, league.id)
        pending.sort(key=_pending_claim_sort_key(settings, priorities))
        for claim in pending:
            priority = priorities.get(claim.team_id)
            if priority is None:
                claim.status = WAIVER_STATUS_FAILED
                claim.failure_reason = "waiver priority missing"
                claim.processed_at = processed_at
                db.add(claim)
                _audit_claim(db, claim, action="failed", actor_user_id=None, reason=claim.failure_reason)
                summary["failed"] += 1
                db.commit()
                continue
            success = _process_single_claim(
                db,
                league=league,
                settings=settings,
                claim=claim,
                priority=priority,
                now=processed_at,
            )
            if success:
                summary["processed"] += 1
            else:
                summary["failed"] += 1
            db.commit()
    remaining_query = db.query(WaiverClaim).filter(WaiverClaim.status == WAIVER_STATUS_PENDING)
    if league_id is not None:
        remaining_query = remaining_query.filter(WaiverClaim.league_id == league_id)
    summary["pending"] = remaining_query.count()
    return summary
