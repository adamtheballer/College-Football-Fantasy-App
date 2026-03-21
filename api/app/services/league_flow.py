from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import generate_invite_code
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.league_flow import (
    DraftRead,
    DraftUpdate,
    LeagueCreateRequest,
    LeagueCreateResponse,
    LeagueDetailRead,
    LeagueSettingsUpdate,
)
from collegefootballfantasy_api.app.services.league_workspace import get_league_detail
from collegefootballfantasy_api.app.services.notification_service import (
    cancel_scheduled_notifications,
    schedule_draft_notifications,
)

FIXED_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}


def enforce_fixed_roster_settings(payload_settings):
    payload_settings.roster_slots_json = FIXED_ROSTER_SLOTS.copy()
    payload_settings.superflex_enabled = False
    payload_settings.kicker_enabled = True
    payload_settings.defense_enabled = False
    return payload_settings


def generate_unique_invite(db: Session) -> str:
    for _ in range(20):
        code = generate_invite_code(20)
        exists = db.query(LeagueInvite).filter(LeagueInvite.code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unable to generate invite code")
def create_league(
    payload: LeagueCreateRequest,
    db: Session,
    current_user: User,
) -> LeagueCreateResponse:
    payload.settings = enforce_fixed_roster_settings(payload.settings)
    code = generate_unique_invite(db)
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

    db.add(
        LeagueSettings(
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
    )

    db.add(
        Draft(
            league_id=league.id,
            draft_datetime_utc=payload.draft.draft_datetime_utc,
            timezone=payload.draft.timezone,
            draft_type=payload.draft.draft_type,
            pick_timer_seconds=payload.draft.pick_timer_seconds,
            status="scheduled",
        )
    )

    db.add(
        LeagueInvite(
            league_id=league.id,
            code=code,
            active=True,
            created_by=current_user.id,
        )
    )

    db.add(
        LeagueMember(
            league_id=league.id,
            user_id=current_user.id,
            role="commissioner",
        )
    )

    db.add(
        Team(
            league_id=league.id,
            name=f"{current_user.first_name}'s Team",
            owner_name=current_user.first_name,
            owner_user_id=current_user.id,
        )
    )

    schedule_draft_notifications(db, league.id, current_user.id, payload.draft.draft_datetime_utc)

    db.commit()
    db.refresh(league)
    detail = get_league_detail(db, league)
    invite_link = f"{settings.ui_base_url.rstrip('/')}/join/{code}"
    return LeagueCreateResponse(league=detail, invite_code=code, invite_link=invite_link)


def join_league(db: Session, league: League, current_user: User) -> LeagueDetailRead:
    existing = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == current_user.id)
        .first()
    )
    if existing:
        return get_league_detail(db, league)

    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    if member_count >= league.max_teams:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="league is full")

    db.add(LeagueMember(league_id=league.id, user_id=current_user.id, role="member"))
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
        schedule_draft_notifications(db, league.id, current_user.id, draft_row.draft_datetime_utc)
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


def regenerate_invite(db: Session, league: League, current_user: User) -> LeagueCreateResponse:
    code = generate_unique_invite(db)
    db.query(LeagueInvite).filter(LeagueInvite.league_id == league.id, LeagueInvite.active.is_(True)).update(
        {"active": False, "disabled_at": datetime.utcnow()}
    )
    db.add(LeagueInvite(league_id=league.id, code=code, active=True, created_by=current_user.id))
    league.invite_code = code
    db.add(league)
    db.commit()
    detail = get_league_detail(db, league)
    invite_link = f"{settings.ui_base_url.rstrip('/')}/join/{code}"
    return LeagueCreateResponse(league=detail, invite_code=code, invite_link=invite_link)


def update_league_settings(
    db: Session,
    league: League,
    payload: LeagueSettingsUpdate,
) -> LeagueDetailRead:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        settings_row = LeagueSettings(league_id=league.id)

    payload = enforce_fixed_roster_settings(payload)
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
    return get_league_detail(db, league)


def reschedule_draft(
    db: Session,
    league: League,
    payload: DraftUpdate,
) -> DraftRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        draft_row = Draft(league_id=league.id)

    draft_row.draft_datetime_utc = payload.draft_datetime_utc
    draft_row.timezone = payload.timezone
    draft_row.draft_type = payload.draft_type
    draft_row.pick_timer_seconds = payload.pick_timer_seconds
    draft_row.status = payload.status
    db.add(draft_row)

    cancel_scheduled_notifications(db, league.id, reason="draft rescheduled")
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()
    for member in members:
        schedule_draft_notifications(db, league.id, member.user_id, draft_row.draft_datetime_utc)

    db.commit()
    db.refresh(draft_row)
    return DraftRead.model_validate(draft_row)
