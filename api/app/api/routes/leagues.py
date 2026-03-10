from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import generate_invite_code
from collegefootballfantasy_api.app.crud.league import delete_league, list_leagues
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.league import LeagueList
from collegefootballfantasy_api.app.schemas.league_flow import (
    DraftRead,
    DraftUpdate,
    LeagueCreateRequest,
    LeagueCreateResponse,
    LeagueDetailRead,
    LeagueMemberRead,
    LeagueMembersList,
    LeaguePreview,
    LeagueSettingsRead,
    LeagueSettingsUpdate,
    JoinByCodeRequest,
)

router = APIRouter()


def _generate_unique_invite(db: Session) -> str:
    for _ in range(20):
        code = generate_invite_code(20)
        exists = db.query(LeagueInvite).filter(LeagueInvite.code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unable to generate invite code")


def _schedule_draft_notifications(
    db: Session, league_id: int, user_id: int, draft_time: datetime
) -> None:
    draft_time = draft_time.astimezone(timezone.utc)
    one_hour_before = draft_time - timedelta(hours=1)
    notifications = [
        ScheduledNotification(
            league_id=league_id,
            user_id=user_id,
            notification_type="draft_1h",
            scheduled_for=one_hour_before,
        ),
        ScheduledNotification(
            league_id=league_id,
            user_id=user_id,
            notification_type="draft_start",
            scheduled_for=draft_time,
        ),
    ]
    db.add_all(notifications)


def _league_detail(db: Session, league: League) -> LeagueDetailRead:
    settings_row = (
        db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    )
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    members_rows = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()

    return LeagueDetailRead(
        id=league.id,
        name=league.name,
        commissioner_user_id=league.commissioner_user_id,
        season_year=league.season_year,
        max_teams=league.max_teams,
        is_private=league.is_private,
        invite_code=league.invite_code,
        description=league.description,
        icon_url=league.icon_url,
        status=league.status,
        created_at=league.created_at,
        updated_at=league.updated_at,
        settings=LeagueSettingsRead.model_validate(settings_row),
        draft=DraftRead.model_validate(draft_row) if draft_row else None,
        members=[LeagueMemberRead.model_validate(m) for m in members_rows],
    )


@router.post("/create", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_flow(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    code = _generate_unique_invite(db)
    league = League(
        name=payload.basics.name,
        platform="custom",
        scoring_type="espn_full_ppr",
        commissioner_user_id=current_user.id,
        season_year=payload.basics.season_year,
        max_teams=payload.basics.max_teams,
        is_private=payload.basics.is_private,
        invite_code=code,
        description=payload.basics.description,
        icon_url=payload.basics.icon_url,
        status="pre_draft",
    )
    db.add(league)
    db.flush()

    settings_row = LeagueSettings(
        league_id=league.id,
        scoring_json=payload.settings.scoring_json,
        roster_slots_json=payload.settings.roster_slots_json,
        playoff_teams=payload.settings.playoff_teams,
        waiver_type=payload.settings.waiver_type,
        trade_review_type=payload.settings.trade_review_type,
        superflex_enabled=payload.settings.superflex_enabled,
        kicker_enabled=payload.settings.kicker_enabled,
        defense_enabled=payload.settings.defense_enabled,
    )
    db.add(settings_row)

    draft_row = Draft(
        league_id=league.id,
        draft_datetime_utc=payload.draft.draft_datetime_utc,
        timezone=payload.draft.timezone,
        draft_type=payload.draft.draft_type,
        pick_timer_seconds=payload.draft.pick_timer_seconds,
        status="scheduled",
    )
    db.add(draft_row)

    invite = LeagueInvite(
        league_id=league.id,
        code=code,
        active=True,
        created_by=current_user.id,
    )
    db.add(invite)

    member = LeagueMember(
        league_id=league.id,
        user_id=current_user.id,
        role="commissioner",
    )
    db.add(member)

    team = Team(
        league_id=league.id,
        name=f"{current_user.first_name}'s Team",
        owner_name=current_user.first_name,
        owner_user_id=current_user.id,
    )
    db.add(team)

    _schedule_draft_notifications(db, league.id, current_user.id, payload.draft.draft_datetime_utc)

    db.commit()
    db.refresh(league)
    detail = _league_detail(db, league)

    invite_link = f"{settings.ui_base_url.rstrip('/')}/join/{code}"
    return LeagueCreateResponse(league=detail, invite_code=code, invite_link=invite_link)


@router.get("", response_model=LeagueList)
def list_leagues_endpoint(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> LeagueList:
    leagues, total = list_leagues(db, limit=limit, offset=offset)
    return LeagueList(data=leagues, total=total, limit=limit, offset=offset)


@router.get("/{league_id}", response_model=LeagueDetailRead)
def get_league_endpoint(league_id: int, db: Session = Depends(get_db)) -> LeagueDetailRead:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return _league_detail(db, league)


@router.get("/{league_id}/members", response_model=LeagueMembersList)
def list_league_members(league_id: int, db: Session = Depends(get_db)) -> LeagueMembersList:
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league_id).all()
    return LeagueMembersList(data=[LeagueMemberRead.model_validate(m) for m in members], total=len(members))


@router.post("/join-by-code", response_model=LeaguePreview)
def join_by_code(payload: JoinByCodeRequest, db: Session = Depends(get_db)) -> LeaguePreview:
    invite = (
        db.query(LeagueInvite)
        .filter(LeagueInvite.code == payload.invite_code.upper(), LeagueInvite.active.is_(True))
        .first()
    )
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite code not found")
    league = db.get(League, invite.league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    commissioner = db.query(User).filter(User.id == league.commissioner_user_id).first()
    return LeaguePreview(
        id=league.id,
        name=league.name,
        commissioner_name=commissioner.first_name if commissioner else None,
        max_teams=league.max_teams,
        member_count=member_count,
        is_private=league.is_private,
        draft_datetime_utc=draft_row.draft_datetime_utc if draft_row else None,
        timezone=draft_row.timezone if draft_row else None,
        scoring_preset=league.scoring_type,
    )


@router.post("/{league_id}/join", response_model=LeagueDetailRead)
def join_league(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    existing = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == current_user.id)
        .first()
    )
    if existing:
        return _league_detail(db, league)
    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    if member_count >= league.max_teams:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="league is full")

    member = LeagueMember(league_id=league.id, user_id=current_user.id, role="member")
    db.add(member)
    db.add(
        Team(
            league_id=league.id,
            name=f"{current_user.first_name}'s Team",
            owner_name=current_user.first_name,
            owner_user_id=current_user.id,
        )
    )
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if draft_row:
        _schedule_draft_notifications(db, league.id, current_user.id, draft_row.draft_datetime_utc)
    db.commit()
    db.refresh(league)
    return _league_detail(db, league)


@router.post("/{league_id}/regenerate-invite", response_model=LeagueCreateResponse)
def regenerate_invite(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    if league.commissioner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner only")
    code = _generate_unique_invite(db)
    db.query(LeagueInvite).filter(LeagueInvite.league_id == league.id, LeagueInvite.active.is_(True)).update(
        {"active": False, "disabled_at": datetime.utcnow()}
    )
    invite = LeagueInvite(league_id=league.id, code=code, active=True, created_by=current_user.id)
    league.invite_code = code
    db.add(invite)
    db.add(league)
    db.commit()
    detail = _league_detail(db, league)
    invite_link = f"{settings.ui_base_url.rstrip('/')}/join/{code}"
    return LeagueCreateResponse(league=detail, invite_code=code, invite_link=invite_link)


@router.patch("/{league_id}/settings", response_model=LeagueDetailRead)
def update_league_settings(
    league_id: int,
    payload: LeagueSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    if league.commissioner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner only")
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        settings_row = LeagueSettings(league_id=league.id)
    settings_row.scoring_json = payload.scoring_json
    settings_row.roster_slots_json = payload.roster_slots_json
    settings_row.playoff_teams = payload.playoff_teams
    settings_row.waiver_type = payload.waiver_type
    settings_row.trade_review_type = payload.trade_review_type
    settings_row.superflex_enabled = payload.superflex_enabled
    settings_row.kicker_enabled = payload.kicker_enabled
    settings_row.defense_enabled = payload.defense_enabled
    db.add(settings_row)
    db.commit()
    return _league_detail(db, league)


@router.patch("/{league_id}/draft", response_model=DraftRead)
def reschedule_draft(
    league_id: int,
    payload: DraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRead:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    if league.commissioner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner only")
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        draft_row = Draft(league_id=league.id)
    draft_row.draft_datetime_utc = payload.draft_datetime_utc
    draft_row.timezone = payload.timezone
    draft_row.draft_type = payload.draft_type
    draft_row.pick_timer_seconds = payload.pick_timer_seconds
    draft_row.status = payload.status
    db.add(draft_row)

    db.query(ScheduledNotification).filter(ScheduledNotification.league_id == league.id).update(
        {"canceled_at": datetime.utcnow()}
    )
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()
    for member in members:
        _schedule_draft_notifications(db, league.id, member.user_id, draft_row.draft_datetime_utc)

    db.commit()
    db.refresh(draft_row)
    return DraftRead.model_validate(draft_row)


@router.delete("/{league_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_league_endpoint(league_id: int, db: Session = Depends(get_db)) -> None:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    delete_league(db, league)
