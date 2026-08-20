"""Server-authoritative permanent mutual rivalry lifecycle."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_rivalry import LeagueRivalry, LeagueRivalryBinding, LeagueRivalryInvite
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.rivalry import (
    LeagueRivalryViewRead, RivalryCandidateRead, RivalryInviteRead, RivalryMatchupRead,
    RivalryRead, RivalrySeriesRead,
)
from collegefootballfantasy_api.app.services.notification_service import queue_notification_event

PENDING = "PENDING"
ACTIVE = "ACTIVE"
INVITE_TTL = timedelta(hours=72)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """SQLite returns timezone-naive DateTime values despite timezone=True."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _manager_name(user: User | None, team: Team) -> str:
    return (user.first_name if user else None) or team.owner_name or team.name


def _user(db: Session, user_id: int | None) -> User | None:
    return db.get(User, user_id) if user_id else None


def _team(db: Session, league_id: int, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=404, detail="team not found in this league")
    return team


def _owned_team(db: Session, league_id: int, user_id: int) -> Team:
    team = db.query(Team).filter(Team.league_id == league_id, Team.owner_user_id == user_id).one_or_none()
    if team is None:
        raise HTTPException(status_code=403, detail="a human-owned team is required for rivalries")
    return team


def _draft_complete(db: Session, league_id: int) -> None:
    draft = db.query(Draft).filter(Draft.league_id == league_id).one_or_none()
    if draft is None or draft.status.lower() != "completed":
        raise HTTPException(status_code=409, detail="rivalries unlock after the draft is completed")


def _is_member(db: Session, league_id: int, user_id: int | None) -> bool:
    return user_id is not None and db.query(LeagueMember.id).filter(
        LeagueMember.league_id == league_id, LeagueMember.user_id == user_id
    ).first() is not None


def expire_pending_invites(db: Session, league_id: int, *, now: datetime | None = None) -> None:
    now = now or _now()
    db.query(LeagueRivalryInvite).filter(
        LeagueRivalryInvite.league_id == league_id,
        LeagueRivalryInvite.status == PENDING,
        LeagueRivalryInvite.expires_at <= now,
    ).update({"status": "EXPIRED", "responded_at": now}, synchronize_session=False)
    db.flush()


def _invite_read(db: Session, invite: LeagueRivalryInvite) -> RivalryInviteRead:
    sender, recipient = _team(db, invite.league_id, invite.sender_team_id), _team(db, invite.league_id, invite.recipient_team_id)
    sender_user, recipient_user = _user(db, sender.owner_user_id), _user(db, recipient.owner_user_id)
    return RivalryInviteRead(
        id=invite.id, league_id=invite.league_id, sender_team_id=sender.id, sender_team_name=sender.name,
        sender_manager_name=_manager_name(sender_user, sender), sender_manager_avatar_url=sender_user.avatar_url if sender_user else None,
        recipient_team_id=recipient.id, recipient_team_name=recipient.name,
        recipient_manager_name=_manager_name(recipient_user, recipient), recipient_manager_avatar_url=recipient_user.avatar_url if recipient_user else None,
        status=invite.status, expires_at=invite.expires_at, created_at=invite.created_at,
    )


def _rivalry_read(db: Session, rivalry: LeagueRivalry, my_team_id: int) -> RivalryRead:
    opponent_id = rivalry.team_b_id if rivalry.team_a_id == my_team_id else rivalry.team_a_id
    opponent = _team(db, rivalry.league_id, opponent_id)
    opponent_user = _user(db, opponent.owner_user_id)
    return RivalryRead(
        id=rivalry.id, league_id=rivalry.league_id, opponent_team_id=opponent.id, opponent_team_name=opponent.name,
        opponent_manager_name=_manager_name(opponent_user, opponent), opponent_manager_avatar_url=opponent_user.avatar_url if opponent_user else None,
        accepted_at=rivalry.accepted_at, status=rivalry.status,
    )


def get_rivalry_view(db: Session, league: League, user: User) -> LeagueRivalryViewRead:
    expire_pending_invites(db, league.id)
    draft = db.query(Draft).filter(Draft.league_id == league.id).one_or_none()
    team = db.query(Team).filter(Team.league_id == league.id, Team.owner_user_id == user.id).one_or_none()
    eligible = bool(team and draft and draft.status.lower() == "completed")
    if not team:
        return LeagueRivalryViewRead(eligible=eligible)
    binding = db.query(LeagueRivalryBinding).filter(
        LeagueRivalryBinding.league_id == league.id, LeagueRivalryBinding.team_id == team.id
    ).one_or_none()
    rivalry = db.get(LeagueRivalry, binding.rivalry_id) if binding else None
    outgoing = db.query(LeagueRivalryInvite).filter(
        LeagueRivalryInvite.league_id == league.id, LeagueRivalryInvite.sender_team_id == team.id,
        LeagueRivalryInvite.status == PENDING,
    ).one_or_none()
    incoming = db.query(LeagueRivalryInvite).filter(
        LeagueRivalryInvite.league_id == league.id, LeagueRivalryInvite.recipient_team_id == team.id,
        LeagueRivalryInvite.status == PENDING,
    ).order_by(LeagueRivalryInvite.created_at.desc()).all()
    bound_ids = {row.team_id for row in db.query(LeagueRivalryBinding).filter(LeagueRivalryBinding.league_id == league.id).all()}
    candidates = []
    if eligible and not binding:
        for candidate in db.query(Team).filter(Team.league_id == league.id, Team.owner_user_id.isnot(None), Team.id != team.id).order_by(Team.name).all():
            if candidate.id in bound_ids or not _is_member(db, league.id, candidate.owner_user_id):
                continue
            manager = _user(db, candidate.owner_user_id)
            candidates.append(RivalryCandidateRead(team_id=candidate.id, team_name=candidate.name, manager_user_id=candidate.owner_user_id, manager_name=_manager_name(manager, candidate), manager_avatar_url=manager.avatar_url if manager else None))
    return LeagueRivalryViewRead(
        eligible=eligible, rivalry=_rivalry_read(db, rivalry, team.id) if rivalry and rivalry.status == ACTIVE else None,
        outgoing_invite=_invite_read(db, outgoing) if outgoing else None,
        incoming_invites=[_invite_read(db, invite) for invite in incoming], candidates=candidates,
    )


def create_invite(db: Session, league: League, sender: User, recipient_team_id: int) -> RivalryInviteRead:
    _draft_complete(db, league.id)
    expire_pending_invites(db, league.id)
    source, recipient = _owned_team(db, league.id, sender.id), _team(db, league.id, recipient_team_id)
    if recipient.owner_user_id is None or recipient.id == source.id or not _is_member(db, league.id, recipient.owner_user_id):
        raise HTTPException(status_code=422, detail="choose another active human manager")
    if db.query(LeagueRivalryBinding.id).filter(LeagueRivalryBinding.league_id == league.id, LeagueRivalryBinding.team_id.in_((source.id, recipient.id))).first():
        raise HTTPException(status_code=409, detail="one of these teams already has a permanent rival")
    reverse = db.query(LeagueRivalryInvite.id).filter(LeagueRivalryInvite.league_id == league.id, LeagueRivalryInvite.sender_team_id == recipient.id, LeagueRivalryInvite.recipient_team_id == source.id, LeagueRivalryInvite.status == PENDING).first()
    if reverse:
        raise HTTPException(status_code=409, detail="this manager already invited you; accept or decline that invite")
    if db.query(LeagueRivalryInvite.id).filter(LeagueRivalryInvite.league_id == league.id, LeagueRivalryInvite.sender_team_id == source.id, LeagueRivalryInvite.status == PENDING).first():
        raise HTTPException(status_code=409, detail="cancel your existing rivalry invitation before sending another")
    invite = LeagueRivalryInvite(league_id=league.id, sender_user_id=sender.id, sender_team_id=source.id, recipient_user_id=recipient.owner_user_id, recipient_team_id=recipient.id, status=PENDING, expires_at=_now() + INVITE_TTL)
    try:
        db.add(invite); db.flush()
        queue_notification_event(db, league_id=league.id, user_id=recipient.owner_user_id, event_type="RIVAL_INVITE_RECEIVED", event_key=f"rival_invite:{invite.id}:{recipient.owner_user_id}", payload={"rivalry_invite_id": invite.id})
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="a rivalry invitation already exists")
    db.refresh(invite)
    return _invite_read(db, invite)


def respond_to_invite(db: Session, league: League, invite_id: int, user: User, *, accept: bool) -> LeagueRivalryViewRead:
    now = _now()
    try:
        invite = db.query(LeagueRivalryInvite).filter(LeagueRivalryInvite.id == invite_id, LeagueRivalryInvite.league_id == league.id).with_for_update().one_or_none()
        if not invite:
            raise HTTPException(status_code=404, detail="rivalry invitation not found")
        if invite.recipient_user_id != user.id:
            raise HTTPException(status_code=403, detail="only the invited manager can respond")
        if invite.status != PENDING:
            raise HTTPException(status_code=409, detail="this rivalry invitation is no longer pending")
        if _as_utc(invite.expires_at) <= now:
            invite.status, invite.responded_at = "EXPIRED", now; db.commit()
            raise HTTPException(status_code=409, detail="this rivalry invitation expired")
        _draft_complete(db, league.id)
        if not accept:
            invite.status, invite.responded_at = "DECLINED", now
            queue_notification_event(db, league_id=league.id, user_id=invite.sender_user_id, event_type="RIVAL_INVITE_DECLINED", event_key=f"rival_declined:{invite.id}:{invite.sender_user_id}", payload={"rivalry_invite_id": invite.id})
            db.commit(); return get_rivalry_view(db, league, user)
        source, recipient = _team(db, league.id, invite.sender_team_id), _team(db, league.id, invite.recipient_team_id)
        if source.owner_user_id != invite.sender_user_id or recipient.owner_user_id != user.id or not _is_member(db, league.id, source.owner_user_id) or not _is_member(db, league.id, recipient.owner_user_id):
            raise HTTPException(status_code=409, detail="team ownership or league membership changed; the invitation is invalid")
        bindings = db.query(LeagueRivalryBinding).filter(LeagueRivalryBinding.league_id == league.id, LeagueRivalryBinding.team_id.in_((source.id, recipient.id))).with_for_update().all()
        if bindings:
            raise HTTPException(status_code=409, detail="one of these teams already has a permanent rival")
        a, b = sorted((source, recipient), key=lambda item: item.id)
        a_user, b_user = _user(db, a.owner_user_id), _user(db, b.owner_user_id)
        rivalry = LeagueRivalry(league_id=league.id, team_a_id=a.id, team_b_id=b.id, user_a_id=a.owner_user_id, user_b_id=b.owner_user_id, team_a_name_snapshot=a.name, team_b_name_snapshot=b.name, manager_a_name_snapshot=_manager_name(a_user, a), manager_b_name_snapshot=_manager_name(b_user, b), accepted_invite_id=invite.id, accepted_at=now, status=ACTIVE)
        db.add(rivalry); db.flush()
        db.add_all([LeagueRivalryBinding(league_id=league.id, team_id=source.id, user_id=source.owner_user_id, rivalry_id=rivalry.id), LeagueRivalryBinding(league_id=league.id, team_id=recipient.id, user_id=recipient.owner_user_id, rivalry_id=rivalry.id)])
        invite.status, invite.responded_at, invite.accepted_rivalry_id = "ACCEPTED", now, rivalry.id
        db.query(LeagueRivalryInvite).filter(LeagueRivalryInvite.league_id == league.id, LeagueRivalryInvite.status == PENDING, LeagueRivalryInvite.id != invite.id, or_(LeagueRivalryInvite.sender_team_id.in_((source.id, recipient.id)), LeagueRivalryInvite.recipient_team_id.in_((source.id, recipient.id)))).update({"status": "INVALIDATED", "responded_at": now}, synchronize_session=False)
        for manager_id in (source.owner_user_id, recipient.owner_user_id):
            queue_notification_event(db, league_id=league.id, user_id=manager_id, event_type="RIVALRY_OFFICIAL", event_key=f"rivalry_official:{rivalry.id}:{manager_id}", payload={"rivalry_id": rivalry.id})
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="rivalry state changed; refresh and try again")
    return get_rivalry_view(db, league, user)


def cancel_invite(db: Session, league: League, invite_id: int, user: User) -> None:
    invite = db.query(LeagueRivalryInvite).filter(LeagueRivalryInvite.id == invite_id, LeagueRivalryInvite.league_id == league.id).one_or_none()
    if not invite: raise HTTPException(status_code=404, detail="rivalry invitation not found")
    if invite.sender_user_id != user.id: raise HTTPException(status_code=403, detail="only the sender can cancel")
    if invite.status != PENDING: raise HTTPException(status_code=409, detail="this rivalry invitation is no longer pending")
    invite.status, invite.responded_at = "CANCELED", _now(); db.commit()


def matchup_rivalry_context(db: Session, league: League, primary_team: Team | None, opponent: Team | None) -> RivalryMatchupRead | None:
    if not primary_team or not opponent:
        return None
    binding = db.query(LeagueRivalryBinding).filter(LeagueRivalryBinding.league_id == league.id, LeagueRivalryBinding.team_id == primary_team.id).one_or_none()
    if not binding: return None
    rivalry = db.get(LeagueRivalry, binding.rivalry_id)
    if not rivalry or rivalry.status != ACTIVE or opponent.id not in (rivalry.team_a_id, rivalry.team_b_id): return None
    wins = losses = ties = 0; last = None
    rows = db.query(Matchup).filter(Matchup.league_id == league.id, Matchup.status.in_(("final", "completed", "stat_corrected", "corrected")), or_(and_(Matchup.home_team_id == primary_team.id, Matchup.away_team_id == opponent.id), and_(Matchup.home_team_id == opponent.id, Matchup.away_team_id == primary_team.id))).order_by(Matchup.season.desc(), Matchup.week.desc(), Matchup.id.desc()).all()
    for row in rows:
        mine, theirs = (row.home_score, row.away_score) if row.home_team_id == primary_team.id else (row.away_score, row.home_score)
        if mine > theirs: wins += 1
        elif mine < theirs: losses += 1
        else: ties += 1
    if rows:
        latest = rows[0]; mine, theirs = (latest.home_score, latest.away_score) if latest.home_team_id == primary_team.id else (latest.away_score, latest.home_score)
        last = f"Week {latest.week}: {mine:.1f}-{theirs:.1f}"
    return RivalryMatchupRead(is_rivalry_matchup=True, rivalry_id=rivalry.id, opponent_team_id=opponent.id, opponent_team_name=opponent.name, series=RivalrySeriesRead(wins=wins, losses=losses, ties=ties, last_meeting=last))
