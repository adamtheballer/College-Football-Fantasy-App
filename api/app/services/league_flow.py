from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.app.core.config import settings
from api.app.core.security import generate_invite_code
from api.app.models.draft import Draft
from api.app.models.league import League
from api.app.models.league_invite import LeagueInvite
from api.app.models.league_member import LeagueMember
from api.app.models.league_settings import LeagueSettings
from api.app.models.team import Team
from api.app.models.user import User
from api.app.schemas.league_flow import (
    DraftRead,
    DraftUpdate,
    LeagueCreateRequest,
    LeagueCreateResponse,
    LeagueDetailRead,
    LeagueSettingsUpdate,
)
from api.app.services.league_workspace import get_league_detail
from api.app.services.notification_service import (
    cancel_scheduled_notifications,
    schedule_draft_notifications,
)

FIXED_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "BENCH": 5,
    "IR": 1,
}


def enforce_fixed_roster_settings(payload_settings):
    payload_settings.roster_slots_json = FIXED_ROSTER_SLOTS.copy()
    payload_settings.superflex_enabled = False
    payload_settings.kicker_enabled = True
    payload_settings.defense_enabled = False
    return payload_settings


def _scoring_with_meta(
    scoring_json: dict,
    *,
    draft_order_strategy: str | None = None,
    skill_mode: str | None = None,
) -> dict:
    payload = dict(scoring_json or {})
    existing_meta = payload.get("__meta__")
    meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    if draft_order_strategy:
        meta["draft_order_strategy"] = draft_order_strategy
    if skill_mode:
        meta["skill_mode"] = skill_mode
    payload["__meta__"] = meta
    return payload


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
    if payload.draft.draft_type != "snake":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only snake draft is supported")
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
            scoring_json=_scoring_with_meta(
                payload.settings.scoring_json,
                draft_order_strategy=payload.draft.order_strategy,
                skill_mode="custom",
            ),
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
    existing_meta = (
        dict(settings_row.scoring_json.get("__meta__", {}))
        if isinstance(settings_row.scoring_json, dict)
        else {}
    )
    merged_scoring = dict(payload.scoring_json or {})
    if existing_meta:
        merged_scoring["__meta__"] = existing_meta
    settings_row.scoring_json = merged_scoring
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
    if payload.draft_type != "snake":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="only snake draft is supported")
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        draft_row = Draft(league_id=league.id)

    draft_row.draft_datetime_utc = payload.draft_datetime_utc
    draft_row.timezone = payload.timezone
    draft_row.draft_type = payload.draft_type
    draft_row.pick_timer_seconds = payload.pick_timer_seconds
    draft_row.status = payload.status
    db.add(draft_row)

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if settings_row:
        settings_row.scoring_json = _scoring_with_meta(
            settings_row.scoring_json or {},
            draft_order_strategy=payload.order_strategy,
        )
        db.add(settings_row)

    cancel_scheduled_notifications(db, league.id, reason="draft rescheduled")
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()
    for member in members:
        schedule_draft_notifications(db, league.id, member.user_id, draft_row.draft_datetime_utc)

    db.commit()
    db.refresh(draft_row)
    return DraftRead.model_validate(draft_row)
