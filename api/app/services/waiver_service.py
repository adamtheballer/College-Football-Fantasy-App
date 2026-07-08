from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.schemas.waiver import WaiverClaimCreate, WaiverClaimList, WaiverClaimRead, WaiverProcessResult
from collegefootballfantasy_api.app.services.audit_service import record_audit_event
from collegefootballfantasy_api.app.services.notification_service import create_notification_event
from collegefootballfantasy_api.app.services.roster_legality import assign_best_roster_slot_for_team
from collegefootballfantasy_api.app.services.roster_lock_service import RosterLockError, ensure_player_unlocked


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _league_member(db: Session, league_id: int, user_id: int) -> LeagueMember:
    membership = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="league membership required")
    return membership


def _league_settings(db: Session, league_id: int) -> LeagueSettings:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return settings


def _team(db: Session, league_id: int, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team not found")
    return team


def _require_team_owner(team: Team, current_user: User) -> None:
    if team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required")


def _player_available(db: Session, league_id: int, player_id: int) -> bool:
    exists = db.query(RosterEntry.id).filter(RosterEntry.league_id == league_id, RosterEntry.player_id == player_id).first()
    return exists is None


def _priority_row(db: Session, *, league_id: int, team_id: int, faab_budget: int) -> WaiverPriority:
    row = (
        db.query(WaiverPriority)
        .filter(WaiverPriority.league_id == league_id, WaiverPriority.team_id == team_id)
        .first()
    )
    if row:
        return row
    max_priority = db.query(WaiverPriority.priority).filter(WaiverPriority.league_id == league_id).all()
    next_priority = len(max_priority) + 1
    row = WaiverPriority(league_id=league_id, team_id=team_id, priority=next_priority, faab_remaining=faab_budget)
    db.add(row)
    db.flush()
    return row


def initialize_waiver_priorities(db: Session, league_id: int) -> None:
    settings = _league_settings(db, league_id)
    teams = db.query(Team).filter(Team.league_id == league_id).order_by(Team.created_at.asc(), Team.id.asc()).all()
    for index, team in enumerate(teams, start=1):
        existing = (
            db.query(WaiverPriority)
            .filter(WaiverPriority.league_id == league_id, WaiverPriority.team_id == team.id)
            .first()
        )
        if not existing:
            db.add(WaiverPriority(league_id=league_id, team_id=team.id, priority=index, faab_remaining=settings.faab_budget))


def _claim_sort_key(claim: WaiverClaim) -> tuple:
    bid = int(claim.bid_amount or 0)
    priority = int(claim.priority_at_submission or 999_999)
    return (-bid, priority, claim.created_at, claim.id)


def _serialize_claim(claim: WaiverClaim) -> WaiverClaimRead:
    return WaiverClaimRead.model_validate(claim)


def submit_waiver_claim(
    db: Session,
    *,
    league: League,
    payload: WaiverClaimCreate,
    current_user: User,
) -> WaiverClaimRead:
    _league_member(db, league.id, current_user.id)
    settings = _league_settings(db, league.id)
    team = _team(db, league.id, payload.team_id)
    _require_team_owner(team, current_user)
    if settings.waiver_mode == "free_agent_only":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="waiver claims are disabled")
    if not db.get(Player, payload.add_player_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="add player not found")
    if not _player_available(db, league.id, payload.add_player_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player is not available")
    drop_player_id = payload.drop_player_id
    if drop_player_id is not None:
        drop_entry = (
            db.query(RosterEntry)
            .filter(RosterEntry.league_id == league.id, RosterEntry.team_id == team.id, RosterEntry.player_id == drop_player_id)
            .first()
        )
        if not drop_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="drop player not found on team")
        try:
            ensure_player_unlocked(db, league, drop_entry.player)
        except RosterLockError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    priority = _priority_row(db, league_id=league.id, team_id=team.id, faab_budget=settings.faab_budget)
    bid_amount = int(payload.bid_amount or 0)
    if settings.waiver_mode == "faab":
        if bid_amount == 0 and not settings.allow_zero_dollar_bids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="zero dollar bids are not allowed")
        if bid_amount > priority.faab_remaining:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bid exceeds FAAB remaining")
    else:
        bid_amount = 0

    claim = WaiverClaim(
        league_id=league.id,
        team_id=team.id,
        add_player_id=payload.add_player_id,
        drop_player_id=drop_player_id,
        bid_amount=bid_amount,
        priority_at_submission=priority.priority,
        status="pending",
        process_after=_utc_now() + timedelta(hours=int(settings.waiver_period_hours or 24)),
    )
    db.add(claim)
    db.flush()
    record_audit_event(
        db,
        action="waiver.claim.submit",
        entity_type="waiver_claim",
        entity_id=claim.id,
        league_id=league.id,
        team_id=team.id,
        actor_user_id=current_user.id,
        after={"add_player_id": claim.add_player_id, "drop_player_id": claim.drop_player_id, "bid_amount": claim.bid_amount},
    )
    db.commit()
    db.refresh(claim)
    return _serialize_claim(claim)


def list_waiver_claims(db: Session, *, league: League, current_user: User) -> WaiverClaimList:
    membership = _league_member(db, league.id, current_user.id)
    query = db.query(WaiverClaim).filter(WaiverClaim.league_id == league.id)
    if membership.role != "commissioner" and league.commissioner_user_id != current_user.id:
        team_ids = [team.id for team in db.query(Team).filter(Team.league_id == league.id, Team.owner_user_id == current_user.id).all()]
        query = query.filter(WaiverClaim.team_id.in_(team_ids or [-1]))
    rows = query.order_by(WaiverClaim.created_at.desc(), WaiverClaim.id.desc()).all()
    return WaiverClaimList(data=[_serialize_claim(row) for row in rows], total=len(rows))


def cancel_waiver_claim(db: Session, *, claim_id: int, current_user: User) -> WaiverClaimRead:
    claim = db.get(WaiverClaim, claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="waiver claim not found")
    team = db.get(Team, claim.team_id)
    if not team or team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required")
    if claim.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"waiver claim is {claim.status}")
    claim.status = "cancelled"
    claim.processed_at = _utc_now()
    record_audit_event(db, action="waiver.claim.cancel", entity_type="waiver_claim", entity_id=claim.id, league_id=claim.league_id, team_id=claim.team_id, actor_user_id=current_user.id)
    db.commit()
    db.refresh(claim)
    return _serialize_claim(claim)


def _fail_claim(db: Session, claim: WaiverClaim, reason: str) -> None:
    claim.status = "failed"
    claim.failure_reason = reason
    claim.processed_at = _utc_now()
    db.add(claim)
    _notify_claim(db, claim, "Waiver Claim Failed", reason)


def _notify_claim(db: Session, claim: WaiverClaim, title: str, body: str) -> None:
    team = db.get(Team, claim.team_id)
    if not team or team.owner_user_id is None:
        return
    alert_type = "WAIVER_PROCESSED" if claim.status == "processed" else "WAIVER_FAILED"
    create_notification_event(
        db,
        user_id=team.owner_user_id,
        league_id=claim.league_id,
        alert_type=alert_type,
        title=title,
        body=body,
        payload={"claim_id": claim.id, "league_id": claim.league_id, "status": claim.status},
        dedupe_key=f"waiver:{claim.id}:{claim.status}:{team.owner_user_id}",
        source_entity_type="waiver_claim",
        source_entity_id=claim.id,
        deep_link=f"/leagues/{claim.league_id}/waivers",
    )


def _process_one_claim(db: Session, claim: WaiverClaim) -> bool:
    league = db.get(League, claim.league_id)
    team = db.get(Team, claim.team_id)
    add_player = db.get(Player, claim.add_player_id)
    if not league or not team or not add_player:
        _fail_claim(db, claim, "league, team, or player missing")
        return False
    settings = _league_settings(db, league.id)
    priority = _priority_row(db, league_id=league.id, team_id=team.id, faab_budget=settings.faab_budget)
    if claim.status != "pending":
        return False
    if not _player_available(db, league.id, claim.add_player_id):
        _fail_claim(db, claim, "player is no longer available")
        return False
    if settings.waiver_mode == "faab" and int(claim.bid_amount or 0) > priority.faab_remaining:
        _fail_claim(db, claim, "insufficient FAAB")
        return False

    drop_entry = None
    if claim.drop_player_id is not None:
        drop_entry = (
            db.query(RosterEntry)
            .filter(RosterEntry.league_id == league.id, RosterEntry.team_id == team.id, RosterEntry.player_id == claim.drop_player_id)
            .with_for_update()
            .first()
        )
        if not drop_entry:
            _fail_claim(db, claim, "drop player is no longer on roster")
            return False
        try:
            ensure_player_unlocked(db, league, drop_entry.player)
        except RosterLockError as exc:
            _fail_claim(db, claim, str(exc))
            return False
        db.delete(drop_entry)
        db.flush()

    slot = assign_best_roster_slot_for_team(
        db,
        team.id,
        add_player.position,
        settings.roster_slots_json,
        superflex_enabled=settings.superflex_enabled,
    )
    if not slot:
        _fail_claim(db, claim, "team roster is full")
        return False
    db.add(RosterEntry(league_id=league.id, team_id=team.id, player_id=add_player.id, slot=slot, status="active"))
    db.add(
        Transaction(
            league_id=league.id,
            team_id=team.id,
            transaction_type="waiver_claim",
            player_id=add_player.id,
            related_player_id=claim.drop_player_id,
            reason=f"Waiver claim {claim.id}",
        )
    )
    if settings.waiver_mode == "faab":
        priority.faab_remaining = max(0, int(priority.faab_remaining) - int(claim.bid_amount or 0))
    else:
        priorities = db.query(WaiverPriority).filter(WaiverPriority.league_id == league.id).order_by(WaiverPriority.priority.asc()).all()
        old_priority = priority.priority
        for row in priorities:
            if row.team_id != team.id and row.priority > old_priority:
                row.priority -= 1
        priority.priority = len(priorities)
    claim.status = "processed"
    claim.processed_at = _utc_now()
    _notify_claim(db, claim, "Waiver Claim Processed", f"{add_player.name} was added to your roster.")
    record_audit_event(
        db,
        action="waiver.claim.process",
        entity_type="waiver_claim",
        entity_id=claim.id,
        league_id=league.id,
        team_id=team.id,
        after={"add_player_id": claim.add_player_id, "drop_player_id": claim.drop_player_id, "bid_amount": claim.bid_amount},
    )
    db.flush()
    return True


def process_waiver_claims(db: Session, *, league_id: int | None = None) -> WaiverProcessResult:
    initialize_scope = db.query(League.id)
    if league_id is not None:
        initialize_scope = initialize_scope.filter(League.id == league_id)
    for row in initialize_scope.all():
        initialize_waiver_priorities(db, int(row[0]))

    query = db.query(WaiverClaim).filter(WaiverClaim.status == "pending", WaiverClaim.process_after <= _utc_now())
    if league_id is not None:
        query = query.filter(WaiverClaim.league_id == league_id)
    claims = sorted(query.with_for_update().all(), key=_claim_sort_key)
    processed = 0
    failed = 0
    skipped = 0
    for claim in claims:
        try:
            if _process_one_claim(db, claim):
                processed += 1
            elif claim.status == "failed":
                failed += 1
            else:
                skipped += 1
        except IntegrityError:
            db.rollback()
            claim = db.get(WaiverClaim, claim.id)
            if claim:
                _fail_claim(db, claim, "waiver processing conflict")
                failed += 1
    db.commit()
    return WaiverProcessResult(processed=processed, failed=failed, skipped=skipped)
