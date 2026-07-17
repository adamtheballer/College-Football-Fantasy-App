from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.draft_room import (
    DraftPickCreate,
    DraftRoomPickRead,
    DraftRoomRead,
    DraftRoomTeamRead,
)
from collegefootballfantasy_api.app.services.draft_completion import finalize_draft_rosters_and_matchups
from collegefootballfantasy_api.app.services.league_flow import FIXED_ROSTER_SLOTS
from collegefootballfantasy_api.app.services.roster_legality import (
    assign_best_roster_slot_for_team,
    normalize_roster_slot_limits,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ordered_draft_teams(db: Session, league_id: int) -> list[Team]:
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    return sorted(teams, key=lambda team: (team.created_at, team.id))


def draft_pick_team_for_number(teams: list[Team], pick_number: int) -> tuple[int, int, Team | None]:
    if not teams:
        return 1, 1, None
    total_teams = len(teams)
    round_number = ((pick_number - 1) // total_teams) + 1
    round_pick = ((pick_number - 1) % total_teams) + 1
    ordered_teams = teams if round_number % 2 == 1 else list(reversed(teams))
    return round_number, round_pick, ordered_teams[round_pick - 1]


PRE_DRAFT_DURATION_SECONDS = 60
PICK_TRANSITION_SECONDS = 3
ACTIVE_DRAFT_STATUSES = {"pre_draft", "on_clock", "transition"}


def _draft_total_picks(settings_row: LeagueSettings, teams: list[Team]) -> int:
    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    return sum(int(value) for value in normalize_roster_slot_limits(roster_slots).values()) * len(teams)


def _draft_teams_are_ready(db: Session, league: League, teams: list[Team]) -> bool:
    del db
    return len(teams) == league.max_teams


def _remaining_seconds(deadline: datetime | None, now: datetime) -> int:
    normalized_deadline = _ensure_aware(deadline)
    if normalized_deadline is None:
        return 0
    return max(0, int((normalized_deadline - now).total_seconds()))


def _transition_to_on_clock(draft_row: Draft, *, pick_number: int, now: datetime) -> None:
    draft_row.status = "on_clock"
    draft_row.current_pick_number = pick_number
    draft_row.current_pick_started_at = now
    draft_row.current_pick_deadline = now + timedelta(seconds=max(1, draft_row.pick_timer_seconds))
    draft_row.transition_ends_at = None
    draft_row.draft_version += 1


def _cpu_pick_is_due(draft_row: Draft, *, now: datetime) -> bool:
    started_at = _ensure_aware(draft_row.current_pick_started_at)
    if started_at is None:
        return False
    return started_at + timedelta(seconds=settings.draft_cpu_pick_delay_seconds) <= now


def start_draft(db: Session, *, league: League, current_user: User) -> DraftRoomRead:
    now = _now()
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if draft_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if current_user.id != league.commissioner_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner access required")
    if draft_row.status != "scheduled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft has already been started")
    scheduled_start = _ensure_aware(draft_row.draft_datetime_utc)
    if scheduled_start is not None and scheduled_start > now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft has not reached its scheduled start time")

    teams = ordered_draft_teams(db, league.id)
    if not _draft_teams_are_ready(db, league, teams):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft requires a full finalized manager order")

    draft_row.status = "pre_draft"
    draft_row.pre_draft_starts_at = now
    draft_row.draft_starts_at = now + timedelta(seconds=PRE_DRAFT_DURATION_SECONDS)
    draft_row.current_pick_number = 0
    draft_row.current_pick_started_at = None
    draft_row.current_pick_deadline = None
    draft_row.transition_ends_at = None
    draft_row.completed_at = None
    draft_row.draft_version += 1
    league.status = "draft_pre_draft"
    db.commit()
    return build_draft_room_state(db, league, current_user)


def build_draft_room_state(db: Session, league: League, current_user: User) -> DraftRoomRead:
    now = _now()
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")

    teams = ordered_draft_teams(db, league.id)
    picks_rows = (
        db.query(DraftPick, Team, Player)
        .join(Team, Team.id == DraftPick.team_id)
        .join(Player, Player.id == DraftPick.player_id)
        .filter(DraftPick.draft_id == draft_row.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )

    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    draft_roster_slots = normalize_roster_slot_limits(roster_slots)
    total_picks = sum(int(value) for value in draft_roster_slots.values()) * len(teams)
    current_pick = draft_row.current_pick_number or (len(picks_rows) + 1)
    current_round, current_round_pick, current_team = draft_pick_team_for_number(teams, current_pick)
    if draft_row.status != "on_clock" or (total_picks and len(picks_rows) >= total_picks):
        current_team = None

    user_team = next((team for team in teams if team.owner_user_id == current_user.id), None)
    league_is_full = _draft_teams_are_ready(db, league, teams)
    can_make_pick = bool(
        league_is_full
        and draft_row.status == "on_clock"
        and current_team
        and current_user.id == current_team.owner_user_id
    )
    countdown_deadline = (
        draft_row.draft_starts_at
        if draft_row.status == "pre_draft"
        else draft_row.current_pick_deadline
        if draft_row.status == "on_clock"
        else draft_row.transition_ends_at
    )

    return DraftRoomRead(
        league_id=league.id,
        draft_id=draft_row.id,
        status=draft_row.status,
        pick_timer_seconds=draft_row.pick_timer_seconds,
        roster_slots=roster_slots,
        teams=[
            DraftRoomTeamRead(
                id=team.id,
                name=team.name,
                owner_user_id=team.owner_user_id,
                owner_name=team.owner_name,
                is_cpu=team.owner_user_id is None,
            )
            for team in teams
        ],
        picks=[
            DraftRoomPickRead(
                id=pick.id,
                overall_pick=pick.overall_pick,
                round_number=pick.round_number,
                round_pick=pick.round_pick,
                team_id=team.id,
                team_name=team.name,
                player_id=player.id,
                player_name=player.name,
                player_position=player.position,
                player_school=player.school,
                made_by_user_id=pick.made_by_user_id,
                auto_pick=pick.auto_pick,
                created_at=pick.created_at,
            )
            for pick, team, player in picks_rows
        ],
        current_pick=current_pick,
        current_round=current_round,
        current_round_pick=current_round_pick,
        current_team_id=current_team.id if current_team else None,
        current_team_name=current_team.name if current_team else None,
        user_team_id=user_team.id if user_team else None,
        can_make_pick=can_make_pick,
        can_start_draft=bool(
            draft_row.status == "scheduled"
            and current_user.id == league.commissioner_user_id
            and league_is_full
            and (_ensure_aware(draft_row.draft_datetime_utc) is None or _ensure_aware(draft_row.draft_datetime_utc) <= now)
        ),
        pre_draft_starts_at=draft_row.pre_draft_starts_at,
        draft_starts_at=draft_row.draft_starts_at,
        current_pick_started_at=draft_row.current_pick_started_at,
        current_pick_deadline=draft_row.current_pick_deadline,
        transition_ends_at=draft_row.transition_ends_at,
        seconds_remaining=_remaining_seconds(countdown_deadline, now),
        draft_version=draft_row.draft_version,
        pick_started_at=draft_row.current_pick_started_at,
        pick_expires_at=draft_row.current_pick_deadline,
        server_time=now,
    )


def _select_auto_pick_player(
    db: Session,
    *,
    league: League,
    draft_row: Draft,
    team: Team,
    settings_row: LeagueSettings,
) -> Player:
    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    drafted_player_ids = select(DraftPick.player_id).where(DraftPick.draft_id == draft_row.id)
    rostered_player_ids = (
        select(RosterEntry.player_id)
        .join(Team, Team.id == RosterEntry.team_id)
        .where(Team.league_id == league.id)
    )
    rank_bucket = case(
        (Player.sheet_adp.isnot(None), 0),
        (Player.cfb27_rank.isnot(None), 1),
        else_=2,
    )
    candidates = (
        db.query(Player)
        .filter(Player.id.not_in(drafted_player_ids), Player.id.not_in(rostered_player_ids))
        .order_by(
            rank_bucket.asc(),
            Player.sheet_adp.asc().nullslast(),
            Player.cfb27_rank.asc().nullslast(),
            Player.sheet_projected_season_points.desc().nullslast(),
            func.lower(Player.name).asc(),
            Player.id.asc(),
        )
        .limit(500)
        .all()
    )
    for candidate in candidates:
        if assign_best_roster_slot_for_team(
            db,
            team.id,
            candidate.position,
            roster_slots,
            superflex_enabled=settings_row.superflex_enabled,
        ):
            return candidate
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no legal auto-pick player available")


def _record_draft_pick(
    db: Session,
    *,
    league: League,
    draft_row: Draft,
    player: Player,
    current_user: User | None,
    auto_pick: bool,
    now: datetime,
    expected_pick_number: int,
    expected_draft_version: int,
) -> None:
    if draft_row.status != "on_clock":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft is not accepting picks")
    if expected_pick_number != draft_row.current_pick_number:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft state changed")
    if expected_draft_version != draft_row.draft_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft state changed")
    if not auto_pick and _ensure_aware(draft_row.current_pick_deadline) and _ensure_aware(draft_row.current_pick_deadline) <= now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="pick expired; waiting for auto-pick")

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if settings_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    teams = ordered_draft_teams(db, league.id)
    if not _draft_teams_are_ready(db, league, teams):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft requires a full finalized manager order")
    expected_count = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
    if draft_row.current_pick_number != expected_count + 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft state changed")
    round_number, round_pick, current_team = draft_pick_team_for_number(teams, draft_row.current_pick_number)
    if current_team is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft cannot determine current team")
    if not auto_pick and (current_user is None or current_user.id != current_team.owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your turn to draft")
    if db.query(DraftPick.id).filter(DraftPick.draft_id == draft_row.id, DraftPick.player_id == player.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already drafted")

    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    roster_slot = assign_best_roster_slot_for_team(
        db,
        current_team.id,
        player.position,
        roster_slots,
        superflex_enabled=settings_row.superflex_enabled,
    )
    if not roster_slot:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no open legal roster slot for this position")

    db.add(
        DraftPick(
            draft_id=draft_row.id,
            team_id=current_team.id,
            player_id=player.id,
            made_by_user_id=current_user.id if current_user else None,
            round_number=round_number,
            round_pick=round_pick,
            overall_pick=draft_row.current_pick_number,
            auto_pick=auto_pick,
        )
    )
    db.add(
        RosterEntry(
            league_id=league.id,
            team_id=current_team.id,
            player_id=player.id,
            slot=roster_slot,
            status="active",
        )
    )
    total_picks = _draft_total_picks(settings_row, teams)
    if draft_row.current_pick_number >= total_picks:
        draft_row.status = "completed"
        draft_row.completed_at = now
        draft_row.current_pick_started_at = None
        draft_row.current_pick_deadline = None
        draft_row.transition_ends_at = None
        league.status = "post_draft"
        finalize_draft_rosters_and_matchups(db, league)
    else:
        draft_row.status = "transition"
        draft_row.current_pick_started_at = None
        draft_row.current_pick_deadline = None
        draft_row.transition_ends_at = now + timedelta(seconds=PICK_TRANSITION_SECONDS)
        league.status = "draft_live"
    draft_row.draft_version += 1


def _auto_pick_current_turn(
    db: Session,
    *,
    league: League,
    draft_row: Draft,
    now: datetime,
) -> None:
    teams = ordered_draft_teams(db, league.id)
    _round, _round_pick, current_team = draft_pick_team_for_number(teams, draft_row.current_pick_number)
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if current_team is None or settings_row is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft state changed")
    player = _select_auto_pick_player(
        db,
        league=league,
        draft_row=draft_row,
        team=current_team,
        settings_row=settings_row,
    )
    _record_draft_pick(
        db,
        league=league,
        draft_row=draft_row,
        player=player,
        current_user=None,
        auto_pick=True,
        now=now,
        expected_pick_number=draft_row.current_pick_number,
        expected_draft_version=draft_row.draft_version,
    )


def auto_pick_expired_draft_pick(
    db: Session,
    *,
    league: League,
    current_user: User,
    now: datetime | None = None,
) -> DraftRoomRead:
    current = _ensure_aware(now or _now())
    try:
        draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
        if draft_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
        if (
            draft_row.status != "on_clock"
            or _ensure_aware(draft_row.current_pick_deadline) is None
            or _ensure_aware(draft_row.current_pick_deadline) > current
        ):
            return build_draft_room_state(db, league, current_user)
        _auto_pick_current_turn(db, league=league, draft_row=draft_row, now=current)
        db.commit()
        return build_draft_room_state(db, league, current_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="auto-pick conflicts with draft state") from exc
    except HTTPException:
        db.rollback()
        raise


def process_expired_draft_picks_once(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Advance pre-draft, transition, and timeout states without a browser client."""
    current = _ensure_aware(now or _now())
    draft_ids = [
        draft_id
        for (draft_id,) in (
            db.query(Draft.id)
            .filter(Draft.status.in_(ACTIVE_DRAFT_STATUSES))
            .order_by(Draft.id.asc())
            .all()
        )
    ]
    summary = {"auto_picked": 0, "skipped": 0}
    for draft_id in draft_ids:
        draft_row = db.query(Draft).filter(Draft.id == draft_id).with_for_update(skip_locked=True).first()
        if draft_row is None:
            continue
        league = db.get(League, draft_row.league_id)
        if league is None:
            summary["skipped"] += 1
            continue
        current_user = db.get(User, league.commissioner_user_id)
        if current_user is None:
            summary["skipped"] += 1
            continue
        before_count = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
        try:
            draft_starts_at = _ensure_aware(draft_row.draft_starts_at)
            transition_ends_at = _ensure_aware(draft_row.transition_ends_at)
            if draft_row.status == "pre_draft" and draft_starts_at is not None and draft_starts_at <= current:
                _transition_to_on_clock(draft_row, pick_number=max(1, draft_row.current_pick_number or 1), now=current)
                league.status = "draft_live"
                db.commit()
            elif draft_row.status == "transition" and transition_ends_at is not None and transition_ends_at <= current:
                settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
                teams = ordered_draft_teams(db, league.id)
                pick_count = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
                if settings_row is None or not teams:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft state changed")
                if pick_count >= _draft_total_picks(settings_row, teams):
                    draft_row.status = "completed"
                    draft_row.completed_at = current
                    draft_row.transition_ends_at = None
                    draft_row.draft_version += 1
                    league.status = "post_draft"
                    finalize_draft_rosters_and_matchups(db, league)
                    db.commit()
                else:
                    _transition_to_on_clock(draft_row, pick_number=pick_count + 1, now=current)
                    db.commit()
            elif draft_row.status == "on_clock":
                teams = ordered_draft_teams(db, league.id)
                _round, _round_pick, current_team = draft_pick_team_for_number(teams, draft_row.current_pick_number)
                deadline = _ensure_aware(draft_row.current_pick_deadline)
                if current_team is None:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft state changed")
                if current_team.owner_user_id is None and _cpu_pick_is_due(draft_row, now=current):
                    _auto_pick_current_turn(db, league=league, draft_row=draft_row, now=current)
                    db.commit()
                elif deadline is not None and deadline <= current:
                    _auto_pick_current_turn(db, league=league, draft_row=draft_row, now=current)
                    db.commit()
                else:
                    summary["skipped"] += 1
                    continue
            else:
                summary["skipped"] += 1
                continue
        except HTTPException:
            # A non-expired or unfillable draft is not a worker failure; it will be retried after state changes.
            db.rollback()
            summary["skipped"] += 1
            continue
        except IntegrityError:
            db.rollback()
            summary["skipped"] += 1
            continue
        after_count = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
        if after_count > before_count:
            summary["auto_picked"] += 1
        else:
            summary["skipped"] += 1
    return summary


def create_real_draft_pick(
    db: Session,
    *,
    league: League,
    payload: DraftPickCreate,
    current_user: User,
) -> DraftRoomRead:
    try:
        now = _now()
        draft_row = (
            db.query(Draft)
            .filter(Draft.league_id == league.id)
            .with_for_update()
            .first()
        )
        if not draft_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

        player = db.get(Player, payload.player_id)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
        _record_draft_pick(
            db,
            league=league,
            draft_row=draft_row,
            player=player,
            current_user=current_user,
            auto_pick=False,
            now=now,
            expected_pick_number=payload.pick_number,
            expected_draft_version=payload.draft_version,
        )

        db.add(draft_row)
        db.add(league)
        db.commit()
        return build_draft_room_state(db, league, current_user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="draft pick conflicts with existing draft or roster state",
        ) from exc
    except HTTPException:
        db.rollback()
        raise
