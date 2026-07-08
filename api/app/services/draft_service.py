from datetime import timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.draft_room import (
    DraftPickCreate,
    DraftRoomPickRead,
    DraftRoomRead,
    DraftRoomTeamRead,
)
from collegefootballfantasy_api.app.services.autopick import (
    best_available_autopick_candidate,
    queued_autopick_candidate,
)
from collegefootballfantasy_api.app.services.audit_service import record_audit_event
from collegefootballfantasy_api.app.services.draft_clock import (
    advance_pick_clock,
    clock_expired,
    draft_timer_seconds,
    ensure_pick_clock,
    pause_pick_clock,
    resume_pick_clock,
    seconds_remaining,
    utc_now,
)
from collegefootballfantasy_api.app.services.draft_completion import finalize_draft_rosters_and_matchups
from collegefootballfantasy_api.app.services.draft_events import record_draft_event
from collegefootballfantasy_api.app.services.league_flow import FIXED_ROSTER_SLOTS
from collegefootballfantasy_api.app.services.roster_legality import (
    assign_best_roster_slot_for_team,
    normalize_roster_slot_limits,
)


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


def _draft_start_is_reached(draft_row: Draft) -> bool:
    draft_start = draft_row.draft_datetime_utc
    if draft_start.tzinfo is None:
        draft_start = draft_start.replace(tzinfo=timezone.utc)
    return draft_start <= utc_now()


def _load_draft_settings(db: Session, league: League) -> tuple[LeagueSettings, dict[str, int], dict[str, int]]:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    draft_roster_slots = normalize_roster_slot_limits(roster_slots)
    return settings_row, roster_slots, draft_roster_slots


def _member_count(db: Session, league: League) -> int:
    return db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()


def _league_is_full(db: Session, league: League) -> bool:
    return _member_count(db, league) >= league.max_teams


def _maybe_start_draft_clock(db: Session, league: League, draft_row: Draft) -> bool:
    if draft_row.status == "scheduled" and _league_is_full(db, league) and _draft_start_is_reached(draft_row):
        draft_row.status = "live"
        league.status = "draft_live"
        ensure_pick_clock(draft_row)
        db.add(draft_row)
        db.add(league)
        db.flush()
        return True
    return False


def _record_draft_pick_transaction(
    db: Session,
    *,
    league_id: int,
    team_id: int,
    player_id: int,
    current_user_id: int | None,
    reason: str,
) -> Transaction:
    row = Transaction(
        league_id=league_id,
        team_id=team_id,
        transaction_type="draft_pick",
        player_id=player_id,
        created_by_user_id=current_user_id,
        reason=reason,
    )
    db.add(row)
    return row


def build_draft_room_state(db: Session, league: League, current_user: User) -> DraftRoomRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    started_clock = _maybe_start_draft_clock(db, league, draft_row)
    if started_clock:
        db.commit()
        db.refresh(draft_row)
        db.refresh(league)

    settings_row, roster_slots, draft_roster_slots = _load_draft_settings(db, league)

    teams = ordered_draft_teams(db, league.id)
    picks_rows = (
        db.query(DraftPick, Team, Player)
        .join(Team, Team.id == DraftPick.team_id)
        .join(Player, Player.id == DraftPick.player_id)
        .filter(DraftPick.draft_id == draft_row.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )

    total_picks = sum(int(value) for value in draft_roster_slots.values()) * len(teams)
    current_pick = len(picks_rows) + 1
    current_round, current_round_pick, current_team = draft_pick_team_for_number(teams, current_pick)
    if total_picks and len(picks_rows) >= total_picks:
        current_team = None

    user_team = next((team for team in teams if team.owner_user_id == current_user.id), None)
    league_is_full = _league_is_full(db, league)
    can_make_pick = bool(
        league_is_full
        and current_team
        and (
            current_user.id == league.commissioner_user_id
            or current_user.id == current_team.owner_user_id
        )
    )

    return DraftRoomRead(
        league_id=league.id,
        draft_id=draft_row.id,
        status=draft_row.status,
        pick_timer_seconds=draft_row.pick_timer_seconds,
        clock_seconds=draft_timer_seconds(draft_row),
        pick_started_at=draft_row.pick_started_at,
        pick_expires_at=draft_row.pick_expires_at,
        seconds_remaining=seconds_remaining(draft_row),
        paused_at=draft_row.paused_at,
        pause_accumulated_seconds=int(draft_row.pause_accumulated_seconds or 0),
        server_time=utc_now(),
        roster_slots=roster_slots,
        teams=[
            DraftRoomTeamRead(
                id=team.id,
                name=team.name,
                owner_user_id=team.owner_user_id,
                owner_name=team.owner_name,
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
    )


def create_real_draft_pick(
    db: Session,
    *,
    league: League,
    payload: DraftPickCreate,
    current_user: User,
) -> DraftRoomRead:
    try:
        draft_row = (
            db.query(Draft)
            .filter(Draft.league_id == league.id)
            .with_for_update()
            .first()
        )
        if not draft_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

        if _member_count(db, league) < league.max_teams:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="draft cannot start until the league is full",
            )

        if draft_row.status == "paused":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft is paused")

        if draft_row.status == "scheduled" and not _draft_start_is_reached(draft_row):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft has not started yet")
        if draft_row.status in {"completed", "cancelled", "reset"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is not active")
        if draft_row.status == "scheduled":
            draft_row.status = "live"
            league.status = "draft_live"
        ensure_pick_clock(draft_row)
        if clock_expired(draft_row):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft pick clock expired")

        settings_row, roster_slots, draft_roster_slots = _load_draft_settings(db, league)

        teams = ordered_draft_teams(db, league.id)
        if not teams:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no teams available for draft")

        existing_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
        total_picks = sum(int(value) for value in draft_roster_slots.values()) * len(teams)
        if total_picks and existing_picks >= total_picks:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")

        round_number, round_pick, current_team = draft_pick_team_for_number(teams, existing_picks + 1)
        if current_team is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft cannot determine current team")

        if current_user.id not in {league.commissioner_user_id, current_team.owner_user_id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your turn to draft")

        player = db.get(Player, payload.player_id)
        if not player:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

        existing_player_pick = (
            db.query(DraftPick)
            .filter(DraftPick.draft_id == draft_row.id, DraftPick.player_id == player.id)
            .first()
        )
        if existing_player_pick:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already drafted")

        existing_roster_entry = (
            db.query(RosterEntry)
            .join(Team, Team.id == RosterEntry.team_id)
            .filter(Team.league_id == league.id, RosterEntry.player_id == player.id)
            .first()
        )
        if existing_roster_entry:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="player already on a league roster")

        slot = assign_best_roster_slot_for_team(
            db,
            current_team.id,
            player.position,
            roster_slots,
            superflex_enabled=settings_row.superflex_enabled,
        )
        if not slot:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No open roster slot for this position.",
            )

        pick = DraftPick(
            draft_id=draft_row.id,
            team_id=current_team.id,
            player_id=player.id,
            made_by_user_id=current_user.id,
            round_number=round_number,
            round_pick=round_pick,
            overall_pick=existing_picks + 1,
        )
        db.add(pick)
        db.flush()

        db.add(
            RosterEntry(
                league_id=league.id,
                team_id=current_team.id,
                player_id=player.id,
                slot=slot,
                status="active",
            )
        )
        db.flush()
        _record_draft_pick_transaction(
            db,
            league_id=league.id,
            team_id=current_team.id,
            player_id=player.id,
            current_user_id=current_user.id,
            reason=f"Draft pick {pick.overall_pick}",
        )

        league.status = "draft_live"
        if total_picks and existing_picks + 1 >= total_picks:
            draft_row.status = "completed"
            draft_row.pick_expires_at = None
            draft_row.pick_started_at = None
            league.status = "post_draft"
            finalize_draft_rosters_and_matchups(db, league)
        else:
            advance_pick_clock(draft_row)

        db.add(draft_row)
        db.add(league)
        record_draft_event(
            db,
            draft=draft_row,
            league_id=league.id,
            event_type="pick_made",
            team_id=current_team.id,
            actor_user_id=current_user.id,
            payload={
                "overall_pick": pick.overall_pick,
                "player_id": player.id,
                "player_name": player.name,
                "autopick": False,
            },
        )
        record_audit_event(
            db,
            action="draft.pick.create",
            entity_type="draft_pick",
            entity_id=pick.id,
            league_id=league.id,
            team_id=current_team.id,
            actor_user_id=current_user.id,
            after={
                "draft_id": draft_row.id,
                "team_id": current_team.id,
                "team_name": current_team.name,
                "player_id": player.id,
                "player_name": player.name,
                "player_position": player.position,
                "round_number": pick.round_number,
                "round_pick": pick.round_pick,
                "overall_pick": pick.overall_pick,
                "assigned_slot": slot,
                "draft_status": draft_row.status,
                "league_status": league.status,
            },
        )
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


def pause_draft(db: Session, *, league: League, current_user: User) -> DraftRoomRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if draft_row.status == "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="completed draft cannot be paused")
    pause_pick_clock(draft_row)
    record_draft_event(
        db,
        draft=draft_row,
        league_id=league.id,
        event_type="paused",
        actor_user_id=current_user.id,
        payload={"status": draft_row.status},
    )
    record_audit_event(
        db,
        action="draft.pause",
        entity_type="draft",
        entity_id=draft_row.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        after={"status": draft_row.status, "paused_at": draft_row.paused_at.isoformat() if draft_row.paused_at else None},
    )
    db.commit()
    return build_draft_room_state(db, league, current_user)


def resume_draft(db: Session, *, league: League, current_user: User) -> DraftRoomRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if draft_row.status != "paused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is not paused")
    resume_pick_clock(draft_row)
    record_draft_event(
        db,
        draft=draft_row,
        league_id=league.id,
        event_type="resumed",
        actor_user_id=current_user.id,
        payload={"status": draft_row.status},
    )
    record_audit_event(
        db,
        action="draft.resume",
        entity_type="draft",
        entity_id=draft_row.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        after={"status": draft_row.status, "pick_expires_at": draft_row.pick_expires_at.isoformat() if draft_row.pick_expires_at else None},
    )
    db.commit()
    return build_draft_room_state(db, league, current_user)


def change_draft_clock(db: Session, *, league: League, clock_seconds: int, current_user: User) -> DraftRoomRead:
    if clock_seconds < 10 or clock_seconds > 600:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="clock_seconds must be between 10 and 600")
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    before = int(draft_row.clock_seconds or draft_row.pick_timer_seconds or 90)
    draft_row.clock_seconds = clock_seconds
    draft_row.pick_timer_seconds = clock_seconds
    if draft_row.status in {"live", "scheduled"} and draft_row.pick_started_at is not None:
        advance_pick_clock(draft_row)
    record_draft_event(
        db,
        draft=draft_row,
        league_id=league.id,
        event_type="clock_changed",
        actor_user_id=current_user.id,
        payload={"before": before, "after": clock_seconds},
    )
    record_audit_event(
        db,
        action="draft.clock.change",
        entity_type="draft",
        entity_id=draft_row.id,
        league_id=league.id,
        actor_user_id=current_user.id,
        before={"clock_seconds": before},
        after={"clock_seconds": clock_seconds},
    )
    db.commit()
    return build_draft_room_state(db, league, current_user)


def undo_last_draft_pick(db: Session, *, league: League, current_user: User) -> DraftRoomRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    last_pick = (
        db.query(DraftPick)
        .filter(DraftPick.draft_id == draft_row.id)
        .order_by(DraftPick.overall_pick.desc())
        .first()
    )
    if not last_pick:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no draft pick to undo")
    roster_entry = (
        db.query(RosterEntry)
        .filter(
            RosterEntry.league_id == league.id,
            RosterEntry.team_id == last_pick.team_id,
            RosterEntry.player_id == last_pick.player_id,
        )
        .first()
    )
    if roster_entry:
        db.delete(roster_entry)
    payload = {
        "overall_pick": last_pick.overall_pick,
        "team_id": last_pick.team_id,
        "player_id": last_pick.player_id,
    }
    db.delete(last_pick)
    draft_row.status = "live"
    league.status = "draft_live"
    advance_pick_clock(draft_row)
    record_draft_event(
        db,
        draft=draft_row,
        league_id=league.id,
        event_type="pick_undone",
        team_id=payload["team_id"],
        actor_user_id=current_user.id,
        payload=payload,
    )
    record_audit_event(
        db,
        action="draft.pick.undo",
        entity_type="draft",
        entity_id=draft_row.id,
        league_id=league.id,
        team_id=payload["team_id"],
        actor_user_id=current_user.id,
        before=payload,
    )
    db.commit()
    return build_draft_room_state(db, league, current_user)


def autopick_expired_draft_pick(db: Session, *, league: League, current_user: User) -> DraftRoomRead:
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).with_for_update().first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")
    if draft_row.status == "paused":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft is paused")
    ensure_pick_clock(draft_row)
    if not clock_expired(draft_row):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft clock has not expired")

    settings_row, roster_slots, draft_roster_slots = _load_draft_settings(db, league)
    teams = ordered_draft_teams(db, league.id)
    existing_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
    total_picks = sum(int(value) for value in draft_roster_slots.values()) * len(teams)
    if total_picks and existing_picks >= total_picks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")
    round_number, round_pick, current_team = draft_pick_team_for_number(teams, existing_picks + 1)
    if current_team is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft cannot determine current team")

    player = queued_autopick_candidate(
        db,
        draft=draft_row,
        league_id=league.id,
        team=current_team,
        roster_slots=roster_slots,
        superflex_enabled=settings_row.superflex_enabled,
    ) or best_available_autopick_candidate(
        db,
        draft=draft_row,
        league_id=league.id,
        team=current_team,
        roster_slots=roster_slots,
        superflex_enabled=settings_row.superflex_enabled,
    )
    if not player:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no legal autopick candidate available")

    slot = assign_best_roster_slot_for_team(
        db,
        current_team.id,
        player.position,
        roster_slots,
        superflex_enabled=settings_row.superflex_enabled,
    )
    if not slot:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no legal autopick slot available")

    pick = DraftPick(
        draft_id=draft_row.id,
        team_id=current_team.id,
        player_id=player.id,
        made_by_user_id=None,
        round_number=round_number,
        round_pick=round_pick,
        overall_pick=existing_picks + 1,
    )
    db.add(pick)
    db.flush()
    db.add(RosterEntry(league_id=league.id, team_id=current_team.id, player_id=player.id, slot=slot, status="active"))
    _record_draft_pick_transaction(
        db,
        league_id=league.id,
        team_id=current_team.id,
        player_id=player.id,
        current_user_id=None,
        reason=f"Autopick {pick.overall_pick}",
    )
    if total_picks and existing_picks + 1 >= total_picks:
        draft_row.status = "completed"
        draft_row.pick_expires_at = None
        draft_row.pick_started_at = None
        league.status = "post_draft"
        finalize_draft_rosters_and_matchups(db, league)
    else:
        draft_row.status = "live"
        league.status = "draft_live"
        advance_pick_clock(draft_row)

    record_draft_event(
        db,
        draft=draft_row,
        league_id=league.id,
        event_type="autopick",
        team_id=current_team.id,
        actor_user_id=current_user.id,
        payload={"overall_pick": pick.overall_pick, "player_id": player.id, "assigned_slot": slot},
    )
    record_audit_event(
        db,
        action="draft.pick.autopick",
        entity_type="draft_pick",
        entity_id=pick.id,
        league_id=league.id,
        team_id=current_team.id,
        actor_user_id=current_user.id,
        after={"overall_pick": pick.overall_pick, "player_id": player.id, "assigned_slot": slot},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft autopick conflicts with existing state") from exc
    return build_draft_room_state(db, league, current_user)
