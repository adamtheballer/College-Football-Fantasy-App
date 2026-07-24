from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
from collegefootballfantasy_api.app.services.chat_service import get_or_create_league_chat_thread
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

DRAFT_FINAL_STATUSES = {"started", "in_progress", "completed", "complete", "final", "closed"}
DRAFT_TYPES = {"snake"}
MIN_PICK_TIMER_SECONDS = 15
MAX_PICK_TIMER_SECONDS = 600

CANONICAL_SCORING_KEYS = {
    "pass_yards",
    "pass_tds",
    "interceptions",
    "rush_yards",
    "rush_tds",
    "receptions",
    "rec_yards",
    "rec_tds",
    "fumbles_lost",
    "fg_made_0_39",
    "fg_made_40_49",
    "fg_made_50_plus",
    "xp_made",
}

SCORING_KEY_ALIASES = {
    "ppr": "receptions",
    "pass_td": "pass_tds",
    "passing_td": "pass_tds",
    "passing_tds": "pass_tds",
    "rush_td": "rush_tds",
    "rushing_td": "rush_tds",
    "rushing_tds": "rush_tds",
    "rec_td": "rec_tds",
    "receiving_td": "rec_tds",
    "receiving_tds": "rec_tds",
    "interception": "interceptions",
    "int": "interceptions",
    "fumble_lost": "fumbles_lost",
    "fg": "fg_made_0_39",
    "xp": "xp_made",
}

YARDS_PER_POINT_SCORING_KEYS = {
    "pass_yds_per_pt": "pass_yards",
    "rush_yds_per_pt": "rush_yards",
    "rec_yds_per_pt": "rec_yards",
}

def _coerce_slot_count(value, minimum: int, maximum: int) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = minimum
    return max(minimum, min(maximum, count))


def _coerce_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _yards_per_point_to_multiplier(value: Any) -> float | None:
    yards_per_point = _coerce_float(value)
    if yards_per_point is None or yards_per_point <= 0:
        return None
    return round(1 / yards_per_point, 6)


def normalize_scoring_settings(scoring_json: dict | None) -> dict:
    normalized: dict[str, float] = {}
    unknown_keys: list[str] = []
    invalid_keys: list[str] = []
    for raw_key, raw_value in (scoring_json or {}).items():
        key = str(raw_key).strip()
        if not key:
            continue
        if key in YARDS_PER_POINT_SCORING_KEYS:
            value = _yards_per_point_to_multiplier(raw_value)
            if value is None:
                invalid_keys.append(key)
            else:
                normalized[YARDS_PER_POINT_SCORING_KEYS[key]] = value
            continue

        canonical_key = SCORING_KEY_ALIASES.get(key, key)
        if canonical_key not in CANONICAL_SCORING_KEYS:
            unknown_keys.append(key)
            continue
        value = _coerce_float(raw_value)
        if value is None:
            invalid_keys.append(key)
        else:
            normalized[canonical_key] = value
    if unknown_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown scoring keys: {', '.join(sorted(unknown_keys))}",
        )
    if invalid_keys:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid scoring values: {', '.join(sorted(invalid_keys))}",
        )
    return normalized


def normalize_roster_settings(payload_settings):
    payload_settings.scoring_json = normalize_scoring_settings(payload_settings.scoring_json)
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
        status="pre_draft",
    )
    db.add(league)
    db.flush()

    # Every league has one master chat thread from creation. Existing leagues are
    # backfilled by the chat migration; this covers all future leagues atomically.
    get_or_create_league_chat_thread(db, league.id)

    db.add(
        LeagueSettings(
            league_id=league.id,
            scoring_json=payload.settings.scoring_json,
            roster_slots_json=payload.settings.roster_slots_json,
            playoff_teams=payload.settings.playoff_teams,
            waiver_type=payload.settings.waiver_type,
            waiver_period_hours=payload.settings.waiver_period_hours,
            waiver_processing_weekday=payload.settings.waiver_processing_weekday,
            waiver_processing_hour=payload.settings.waiver_processing_hour,
            waiver_timezone=payload.settings.waiver_timezone,
            faab_starting_budget=payload.settings.faab_starting_budget,
            allow_zero_faab_bids=payload.settings.allow_zero_faab_bids,
            reveal_all_waiver_bids=payload.settings.reveal_all_waiver_bids,
            waiver_tiebreaker=payload.settings.waiver_tiebreaker,
            initial_waiver_priority_method=payload.settings.initial_waiver_priority_method,
            post_drop_waiver_hours=payload.settings.post_drop_waiver_hours,
            trade_review_type=payload.settings.trade_review_type,
            trade_deadline_week=payload.settings.trade_deadline_week,
            trade_deadline_at=payload.settings.trade_deadline_at,
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
    detail = get_league_detail(db, league, viewer=current_user)
    invite_link = f"{settings.ui_base_url.rstrip('/')}/join/{code}"
    return LeagueCreateResponse(league=detail, invite_code=code, invite_link=invite_link)


def join_league(db: Session, league: League, current_user: User) -> LeagueDetailRead:
    existing = (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league.id, LeagueMember.user_id == current_user.id)
        .first()
    )
    if existing:
        return get_league_detail(db, league, viewer=current_user)

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
    return get_league_detail(db, league, viewer=current_user)


def regenerate_invite(db: Session, league: League, current_user: User) -> LeagueCreateResponse:
    code = generate_unique_invite(db)
    db.query(LeagueInvite).filter(LeagueInvite.league_id == league.id, LeagueInvite.active.is_(True)).update(
        {"active": False, "disabled_at": datetime.utcnow()}
    )
    db.add(LeagueInvite(league_id=league.id, code=code, active=True, created_by=current_user.id))
    league.invite_code = code
    db.add(league)
    db.commit()
    detail = get_league_detail(db, league, viewer=current_user)
    invite_link = f"{settings.ui_base_url.rstrip('/')}/join/{code}"
    return LeagueCreateResponse(league=detail, invite_code=code, invite_link=invite_link)


def revoke_invite(db: Session, league: League, current_user: User) -> LeagueDetailRead:
    db.query(LeagueInvite).filter(LeagueInvite.league_id == league.id, LeagueInvite.active.is_(True)).update(
        {"active": False, "disabled_at": datetime.utcnow()}
    )
    league.invite_code = None
    db.add(league)
    db.commit()
    return get_league_detail(db, league, viewer=current_user)


def update_league_settings(
    db: Session,
    league: League,
    payload: LeagueSettingsUpdate,
    current_user: User,
) -> LeagueDetailRead:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        settings_row = LeagueSettings(league_id=league.id)

    payload = normalize_roster_settings(payload)
    settings_row.scoring_json = payload.scoring_json
    settings_row.roster_slots_json = payload.roster_slots_json
    settings_row.playoff_teams = payload.playoff_teams
    settings_row.waiver_type = payload.waiver_type
    if payload.waiver_period_hours is not None:
        settings_row.waiver_period_hours = payload.waiver_period_hours
    if payload.waiver_processing_weekday is not None:
        settings_row.waiver_processing_weekday = payload.waiver_processing_weekday
    if payload.waiver_processing_hour is not None:
        settings_row.waiver_processing_hour = payload.waiver_processing_hour
    if payload.waiver_timezone is not None:
        settings_row.waiver_timezone = payload.waiver_timezone
    if payload.faab_starting_budget is not None:
        settings_row.faab_starting_budget = payload.faab_starting_budget
    if payload.allow_zero_faab_bids is not None:
        settings_row.allow_zero_faab_bids = payload.allow_zero_faab_bids
    if payload.reveal_all_waiver_bids is not None:
        settings_row.reveal_all_waiver_bids = payload.reveal_all_waiver_bids
    if payload.waiver_tiebreaker is not None:
        settings_row.waiver_tiebreaker = payload.waiver_tiebreaker
    if payload.initial_waiver_priority_method is not None:
        settings_row.initial_waiver_priority_method = payload.initial_waiver_priority_method
    if payload.post_drop_waiver_hours is not None:
        settings_row.post_drop_waiver_hours = payload.post_drop_waiver_hours
    settings_row.trade_review_type = payload.trade_review_type
    settings_row.trade_deadline_week = payload.trade_deadline_week
    settings_row.trade_deadline_at = payload.trade_deadline_at
    settings_row.superflex_enabled = payload.superflex_enabled
    settings_row.kicker_enabled = payload.kicker_enabled
    settings_row.defense_enabled = payload.defense_enabled
    db.add(settings_row)
    db.commit()
    return get_league_detail(db, league, viewer=current_user)


def reschedule_draft(
    db: Session,
    league: League,
    payload: DraftUpdate,
) -> DraftRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        draft_row = Draft(league_id=league.id)

    if league.status not in {"pre_draft", "scheduled"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft can only be rescheduled before the draft starts",
        )
    if (draft_row.status or "").lower() in DRAFT_FINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="started or completed drafts cannot be rescheduled",
        )

    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid draft timezone") from exc

    draft_type = payload.draft_type.strip().lower()
    if draft_type not in DRAFT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid draft type")

    if not MIN_PICK_TIMER_SECONDS <= payload.pick_timer_seconds <= MAX_PICK_TIMER_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pick timer must be between {MIN_PICK_TIMER_SECONDS} and {MAX_PICK_TIMER_SECONDS} seconds",
        )

    next_draft_time = payload.draft_datetime_utc
    if next_draft_time.tzinfo is None:
        next_draft_time = next_draft_time.replace(tzinfo=timezone.utc)
    next_draft_time = next_draft_time.astimezone(timezone.utc)
    if next_draft_time <= datetime.now(timezone.utc) + timedelta(minutes=5):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="draft time must be at least 5 minutes in the future",
        )

    draft_row.draft_datetime_utc = next_draft_time
    draft_row.timezone = payload.timezone
    draft_row.draft_type = draft_type
    draft_row.pick_timer_seconds = payload.pick_timer_seconds
    draft_row.status = "scheduled"
    db.add(draft_row)

    cancel_scheduled_notifications(db, league.id, reason="draft rescheduled")
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()
    for member in members:
        schedule_draft_notifications(db, league.id, member.user_id, draft_row.draft_datetime_utc)

    db.commit()
    db.refresh(draft_row)
    return DraftRead.model_validate(draft_row)
