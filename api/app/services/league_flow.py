from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import generate_invite_code
from collegefootballfantasy_api.app.domain.league_lifecycle import has_draft_started, has_season_started
from collegefootballfantasy_api.app.domain.league_settings import (
    league_settings_snapshot,
    payload_settings_snapshot,
    roster_settings_changed,
    scoring_settings_changed,
)
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.league_settings_version import LeagueSettingsVersion
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.roster import RosterEntry
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
from collegefootballfantasy_api.app.services.audit_service import record_audit_event
from collegefootballfantasy_api.app.services.league_workspace import get_league_detail
from collegefootballfantasy_api.app.services.notification_service import (
    cancel_scheduled_notifications,
    schedule_draft_notifications,
)

FIXED_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "FLEX": 1,
    "TE": 1,
    "SUPERFLEX": 0,
    "K": 1,
    "BENCH": 5,
    "IR": 1,
}

ROSTER_SLOT_BOUNDS = {
    "QB": (1, 3),
    "RB": (1, 5),
    "WR": (1, 5),
    "TE": (1, 3),
    "FLEX": (0, 3),
    "SUPERFLEX": (0, 2),
    "K": (0, 2),
    "BENCH": (0, 10),
    "IR": (0, 4),
}

def _coerce_slot_count(value, minimum: int, maximum: int) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = minimum
    return max(minimum, min(maximum, count))


def normalize_roster_settings(payload_settings):
    raw_slots = payload_settings.roster_slots_json or FIXED_ROSTER_SLOTS
    normalized_slots: dict[str, int] = {}

    for raw_key, raw_value in raw_slots.items():
        key = str(raw_key).strip().upper()
        if key == "BE":
            key = "BENCH"
        if key not in ROSTER_SLOT_BOUNDS:
            continue
        minimum, maximum = ROSTER_SLOT_BOUNDS[key]
        normalized_slots[key] = _coerce_slot_count(raw_value, minimum, maximum)

    if not normalized_slots:
        normalized_slots = FIXED_ROSTER_SLOTS.copy()

    if payload_settings.superflex_enabled:
        normalized_slots["SUPERFLEX"] = max(1, normalized_slots.get("SUPERFLEX", 0))
    else:
        normalized_slots["SUPERFLEX"] = 0

    if payload_settings.kicker_enabled:
        normalized_slots["K"] = max(1, normalized_slots.get("K", 0))
    else:
        normalized_slots["K"] = 0

    payload_settings.roster_slots_json = normalized_slots
    return payload_settings


def generate_unique_invite(db: Session) -> str:
    for _ in range(20):
        code = generate_invite_code(20)
        exists = db.query(LeagueInvite).filter(LeagueInvite.code == code).first()
        if not exists:
            return code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unable to generate invite code")


def _available_team_name(db: Session, league_id: int, owner_name: str) -> str:
    base_name = f"{owner_name}'s Team"
    existing_names = {
        name
        for (name,) in db.query(Team.name)
        .filter(Team.league_id == league_id, Team.name.like(f"{base_name}%"))
        .all()
    }
    if base_name not in existing_names:
        return base_name

    suffix = 2
    while f"{base_name} {suffix}" in existing_names:
        suffix += 1
    return f"{base_name} {suffix}"


def _current_draft(db: Session, league_id: int) -> Draft | None:
    return db.query(Draft).filter(Draft.league_id == league_id).first()


def _league_has_draft_picks(db: Session, league_id: int) -> bool:
    draft_row = _current_draft(db, league_id)
    if not draft_row:
        return False
    return db.query(DraftPick.id).filter(DraftPick.draft_id == draft_row.id).first() is not None


def _league_has_completed_games(db: Session, league_id: int) -> bool:
    return (
        db.query(Matchup.id)
        .filter(
            Matchup.league_id == league_id,
            Matchup.status.in_(["final", "stat_corrected", "commissioner_adjusted"]),
        )
        .first()
        is not None
    )


def _next_settings_version(db: Session, league_id: int) -> int:
    latest = (
        db.query(LeagueSettingsVersion.version)
        .filter(LeagueSettingsVersion.league_id == league_id)
        .order_by(LeagueSettingsVersion.version.desc())
        .first()
    )
    return (latest[0] if latest else 0) + 1


def _record_settings_version(
    db: Session,
    *,
    league: League,
    settings_json: dict,
    current_user: User,
    effective_week: int = 1,
) -> LeagueSettingsVersion:
    version = LeagueSettingsVersion(
        league_id=league.id,
        version=_next_settings_version(db, league.id),
        settings_json=settings_json,
        effective_season=league.season_year,
        effective_week=effective_week,
        created_by=current_user.id,
    )
    db.add(version)
    return version


def _validate_invite_for_join(invite: LeagueInvite, current_user: User) -> None:
    now = datetime.now(timezone.utc)
    expires_at = invite.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not invite.active or invite.revoked_at is not None or invite.disabled_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite code not found")
    if expires_at is not None and expires_at <= now:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="invite code expired")
    if invite.max_uses is not None and invite.uses_count >= invite.max_uses:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="invite code max uses reached")
    if invite.email_domain:
        email_domain = current_user.email.rsplit("@", 1)[-1].lower()
        if email_domain != invite.email_domain.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invite email domain restricted")


def create_league(
    payload: LeagueCreateRequest,
    db: Session,
    current_user: User,
) -> LeagueCreateResponse:
    payload.settings = normalize_roster_settings(payload.settings)
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
        status="draft_scheduled",
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
    _record_settings_version(
        db,
        league=league,
        settings_json=league_settings_snapshot(settings_row),
        current_user=current_user,
    )

    db.add(
        Draft(
            league_id=league.id,
            draft_datetime_utc=payload.draft.draft_datetime_utc,
            timezone=payload.draft.timezone,
            draft_type=payload.draft.draft_type,
            pick_timer_seconds=payload.draft.pick_timer_seconds,
            clock_seconds=payload.draft.pick_timer_seconds,
            status="scheduled",
        )
    )

    db.add(
        LeagueInvite(
            league_id=league.id,
            code=code,
            active=True,
            created_by=current_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            max_uses=league.max_teams,
            uses_count=0,
        )
    )

    db.add(
        LeagueMember(
            league_id=league.id,
            user_id=current_user.id,
            role="commissioner",
        )
    )

    team = Team(
        league_id=league.id,
        name=_available_team_name(db, league.id, current_user.first_name),
        owner_name=current_user.first_name,
        owner_user_id=current_user.id,
    )
    db.add(team)
    db.flush()

    schedule_draft_notifications(db, league.id, current_user.id, payload.draft.draft_datetime_utc)
    record_audit_event(
        db,
        action="league.create",
        entity_type="league",
        entity_id=league.id,
        league_id=league.id,
        team_id=team.id,
        actor_user_id=current_user.id,
        after={
            "league": {
                "id": league.id,
                "name": league.name,
                "season_year": league.season_year,
                "max_teams": league.max_teams,
                "is_private": league.is_private,
                "status": league.status,
            },
            "settings": {
                "scoring_json": payload.settings.scoring_json,
                "roster_slots_json": payload.settings.roster_slots_json,
                "playoff_teams": payload.settings.playoff_teams,
                "waiver_type": payload.settings.waiver_type,
                "trade_review_type": payload.settings.trade_review_type,
                "superflex_enabled": payload.settings.superflex_enabled,
                "kicker_enabled": payload.settings.kicker_enabled,
                "defense_enabled": payload.settings.defense_enabled,
            },
            "draft": {
                "draft_datetime_utc": payload.draft.draft_datetime_utc,
                "timezone": payload.draft.timezone,
                "draft_type": payload.draft.draft_type,
                "pick_timer_seconds": payload.draft.pick_timer_seconds,
            },
        },
    )

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

    invite = (
        db.query(LeagueInvite)
        .filter(LeagueInvite.league_id == league.id, LeagueInvite.code == league.invite_code)
        .first()
    )
    if invite:
        _validate_invite_for_join(invite, current_user)

    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    if member_count >= league.max_teams:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="league is full")

    db.add(LeagueMember(league_id=league.id, user_id=current_user.id, role="member"))
    team = Team(
        league_id=league.id,
        name=_available_team_name(db, league.id, current_user.first_name),
        owner_name=current_user.first_name,
        owner_user_id=current_user.id,
    )
    db.add(team)
    db.flush()
    if invite:
        invite.uses_count += 1
        if invite.max_uses is not None and invite.uses_count >= invite.max_uses:
            invite.active = False
            invite.disabled_at = datetime.now(timezone.utc)
        db.add(invite)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if draft_row:
        schedule_draft_notifications(db, league.id, current_user.id, draft_row.draft_datetime_utc)
    record_audit_event(
        db,
        action="league.join",
        entity_type="league_member",
        entity_id=current_user.id,
        league_id=league.id,
        team_id=team.id,
        actor_user_id=current_user.id,
        after={
            "league_id": league.id,
            "user_id": current_user.id,
            "team_id": team.id,
            "role": "member",
            "member_count": member_count + 1,
        },
    )
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


def regenerate_invite(db: Session, league: League, current_user: User) -> LeagueCreateResponse:
    old_code = league.invite_code
    code = generate_unique_invite(db)
    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    remaining_uses = max(1, league.max_teams - member_count)
    db.query(LeagueInvite).filter(LeagueInvite.league_id == league.id, LeagueInvite.active.is_(True)).update(
        {"active": False, "disabled_at": datetime.now(timezone.utc), "revoked_at": datetime.now(timezone.utc)}
    )
    db.add(
        LeagueInvite(
            league_id=league.id,
            code=code,
            active=True,
            created_by=current_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            max_uses=remaining_uses,
            uses_count=0,
        )
    )
    league.invite_code = code
    db.add(league)
    record_audit_event(
        db,
        action="league.invite.regenerate",
        entity_type="league",
        entity_id=league.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before={"invite_code": old_code},
        after={"invite_code": code},
    )
    db.commit()
    detail = get_league_detail(db, league)
    invite_link = f"{settings.ui_base_url.rstrip('/')}/join/{code}"
    return LeagueCreateResponse(league=detail, invite_code=code, invite_link=invite_link)


def update_league_settings(
    db: Session,
    league: League,
    payload: LeagueSettingsUpdate,
    current_user: User,
) -> LeagueDetailRead:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        settings_row = LeagueSettings(league_id=league.id)
    before = league_settings_snapshot(settings_row)

    payload = normalize_roster_settings(payload)
    after = payload_settings_snapshot(payload)
    draft_row = _current_draft(db, league.id)
    draft_started = has_draft_started(league.status, draft_row.status if draft_row else None) or _league_has_draft_picks(db, league.id)
    if draft_started and roster_settings_changed(before, after):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="roster size cannot be changed after draft starts",
        )

    settings_version = _record_settings_version(
        db,
        league=league,
        settings_json=after,
        current_user=current_user,
        effective_week=2 if has_season_started(league.status) and scoring_settings_changed(before, after) else 1,
    )

    settings_row.scoring_json = payload.scoring_json
    settings_row.roster_slots_json = payload.roster_slots_json
    settings_row.playoff_teams = payload.playoff_teams
    settings_row.waiver_type = payload.waiver_type
    settings_row.trade_review_type = payload.trade_review_type
    settings_row.superflex_enabled = payload.superflex_enabled
    settings_row.kicker_enabled = payload.kicker_enabled
    settings_row.defense_enabled = payload.defense_enabled
    db.add(settings_row)
    record_audit_event(
        db,
        action="league.settings.update",
        entity_type="league_settings",
        entity_id=league.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before=before,
        after={
            **league_settings_snapshot(settings_row),
            "settings_version": settings_version.version,
        },
    )
    db.commit()
    return get_league_detail(db, league)


def reschedule_draft(
    db: Session,
    league: League,
    payload: DraftUpdate,
    current_user: User,
) -> DraftRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        draft_row = Draft(league_id=league.id)
    before = {
        "draft_datetime_utc": draft_row.draft_datetime_utc,
        "timezone": draft_row.timezone,
        "draft_type": draft_row.draft_type,
        "pick_timer_seconds": draft_row.pick_timer_seconds,
        "status": draft_row.status,
    }

    draft_row.draft_datetime_utc = payload.draft_datetime_utc
    draft_row.timezone = payload.timezone
    draft_row.draft_type = payload.draft_type
    draft_row.pick_timer_seconds = payload.pick_timer_seconds
    draft_row.clock_seconds = payload.pick_timer_seconds
    draft_row.pick_started_at = None
    draft_row.pick_expires_at = None
    draft_row.paused_at = None
    draft_row.pause_accumulated_seconds = 0
    draft_row.status = payload.status
    db.add(draft_row)

    cancel_scheduled_notifications(db, league.id, reason="draft rescheduled")
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()
    for member in members:
        schedule_draft_notifications(db, league.id, member.user_id, draft_row.draft_datetime_utc)

    record_audit_event(
        db,
        action="league.draft.reschedule",
        entity_type="draft",
        entity_id=draft_row.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before=before,
        after={
            "draft_datetime_utc": draft_row.draft_datetime_utc,
            "timezone": draft_row.timezone,
            "draft_type": draft_row.draft_type,
            "pick_timer_seconds": draft_row.pick_timer_seconds,
            "status": draft_row.status,
        },
    )
    db.commit()
    db.refresh(draft_row)
    return DraftRead.model_validate(draft_row)


def archive_league(db: Session, league: League, current_user: User) -> LeagueDetailRead:
    before = {"status": league.status}
    league.status = "archived"
    db.add(league)
    record_audit_event(
        db,
        action="league.archive",
        entity_type="league",
        entity_id=league.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before=before,
        after={"status": league.status},
    )
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


def transfer_commissioner(
    db: Session,
    league: League,
    *,
    target_user_id: int,
    current_user: User,
) -> LeagueDetailRead:
    target_member = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == target_user_id)
        .first()
    )
    if not target_member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target member not found")

    old_commissioner_id = league.commissioner_user_id
    old_member = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == old_commissioner_id)
        .first()
    )
    if old_member:
        old_member.role = "member"
        db.add(old_member)

    target_member.role = "commissioner"
    league.commissioner_user_id = target_user_id
    db.add_all([league, target_member])
    record_audit_event(
        db,
        action="league.commissioner.transfer",
        entity_type="league",
        entity_id=league.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before={"commissioner_user_id": old_commissioner_id},
        after={"commissioner_user_id": target_user_id},
    )
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


def remove_member(
    db: Session,
    league: League,
    *,
    target_user_id: int,
    current_user: User,
) -> LeagueDetailRead:
    if target_user_id == league.commissioner_user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="transfer commissioner before removing this member")
    if _league_has_completed_games(db, league.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot remove members after completed games")

    member = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == target_user_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")

    team = db.query(Team).filter(Team.league_id == league.id, Team.owner_user_id == target_user_id).first()
    if team:
        draft = _current_draft(db, league.id)
        has_picks = bool(draft and db.query(DraftPick.id).filter(DraftPick.draft_id == draft.id, DraftPick.team_id == team.id).first())
        if has_picks:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot remove member after their team has draft picks")
        db.delete(team)

    db.delete(member)
    record_audit_event(
        db,
        action="league.member.remove",
        entity_type="league_member",
        entity_id=member.id,
        league_id=league.id,
        team_id=team.id if team else None,
        actor_user_id=current_user.id,
        before={"user_id": target_user_id, "role": member.role},
    )
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


def reset_draft(db: Session, league: League, current_user: User) -> LeagueDetailRead:
    if _league_has_completed_games(db, league.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot reset draft after completed games")

    draft = _current_draft(db, league.id)
    deleted_picks = 0
    if draft:
        deleted_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft.id).delete(synchronize_session=False)
        draft.status = "scheduled"
        draft.pick_started_at = None
        draft.pick_expires_at = None
        draft.paused_at = None
        draft.pause_accumulated_seconds = 0
        db.add(draft)
    deleted_rosters = db.query(RosterEntry).filter(RosterEntry.league_id == league.id).delete(synchronize_session=False)
    deleted_matchups = db.query(Matchup).filter(Matchup.league_id == league.id).delete(synchronize_session=False)
    before = {"status": league.status}
    league.status = "draft_scheduled"
    db.add(league)
    record_audit_event(
        db,
        action="league.draft.reset",
        entity_type="league",
        entity_id=league.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before=before,
        after={
            "status": league.status,
            "deleted_picks": deleted_picks,
            "deleted_rosters": deleted_rosters,
            "deleted_matchups": deleted_matchups,
        },
    )
    db.commit()
    db.refresh(league)
    return get_league_detail(db, league)


def delete_league_with_lifecycle_guard(db: Session, league: League, current_user: User) -> None:
    if _league_has_completed_games(db, league.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="league has completed games and must be archived instead of deleted",
        )
    record_audit_event(
        db,
        action="league.delete",
        entity_type="league",
        entity_id=league.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before={"status": league.status, "name": league.name},
    )
    db.delete(league)
    db.commit()
