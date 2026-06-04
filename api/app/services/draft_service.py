from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.app.models.draft import Draft
from api.app.models.draft_pick import DraftPick
from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.models.user import User
from api.app.schemas.draft_room import DraftPickCreate, DraftRoomRead


def get_draft_room_state(db: Session, league: League, current_user: User) -> DraftRoomRead:
    from api.app.api.routes import leagues as league_routes

    return league_routes._draft_room_state(db, league, current_user)


def get_ordered_draft_teams(db: Session, league_id: int) -> list[Team]:
    from api.app.api.routes import leagues as league_routes

    return league_routes._ordered_draft_teams(db, league_id)


def get_draft_pick_team_for_number(
    teams: list[Team],
    pick_number: int,
) -> tuple[int, int, Team | None]:
    if not teams or pick_number <= 0:
        return 0, 0, None
    team_count = len(teams)
    round_number = ((pick_number - 1) // team_count) + 1
    zero_based_round_pick = (pick_number - 1) % team_count
    round_pick = zero_based_round_pick + 1
    index = zero_based_round_pick if round_number % 2 == 1 else team_count - 1 - zero_based_round_pick
    return round_number, round_pick, teams[index]


def assign_draft_roster_slot(
    db: Session,
    settings_row: LeagueSettings,
    team_id: int,
    player_position: str,
) -> str:
    from api.app.api.routes import leagues as league_routes

    return league_routes._assign_roster_slot(db, settings_row, team_id, player_position)


def _draft_conflict_detail(exc: IntegrityError) -> str:
    raw = str(getattr(exc, "orig", exc)).lower()
    if "idempotency" in raw:
        return "draft state changed; refresh and try again"
    if "roster" in raw or "league_player" in raw or "team_player" in raw:
        return "player already on a league roster"
    if "player" in raw or "draft_player" in raw:
        return "player already drafted"
    return "draft state changed; refresh and try again"


def create_real_draft_pick(
    db: Session,
    league: League,
    payload: DraftPickCreate,
    current_user: User,
    *,
    idempotency_key: str | None = None,
) -> DraftRoomRead:
    from api.app.api.routes import leagues as league_routes

    league_routes.require_league_member(db, league.id, current_user)
    resolved_idempotency_key = (idempotency_key or "").strip() or None

    if resolved_idempotency_key:
        existing_for_key = (
            db.query(DraftPick)
            .join(Draft, Draft.id == DraftPick.draft_id)
            .filter(
                Draft.league_id == league.id,
                DraftPick.idempotency_key == resolved_idempotency_key,
            )
            .first()
        )
        if existing_for_key:
            if existing_for_key.player_id != payload.player_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key already used with a different player.",
                )
            return get_draft_room_state(db, league, current_user)

    try:
        with db.begin_nested():
            draft_row = (
                db.query(Draft)
                .filter(Draft.league_id == league.id)
                .with_for_update()
                .first()
            )
            if not draft_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

            if draft_row.status == "completed":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")
            if draft_row.status != "live":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="draft is not active")

            settings_row = (
                db.query(LeagueSettings)
                .filter(LeagueSettings.league_id == league.id)
                .with_for_update()
                .first()
            )
            if not settings_row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
            timer_state = league_routes._get_or_create_draft_timer_state(db, draft_row.id)

            teams = get_ordered_draft_teams(db, league.id)
            if not teams:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no teams available for draft")

            existing_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
            total_picks = league_routes._total_draft_picks_for_league(settings_row=settings_row, team_count=len(teams))
            if total_picks and existing_picks >= total_picks:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")

            round_number, round_pick, current_team = get_draft_pick_team_for_number(teams, existing_picks + 1)
            if current_team is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft cannot determine current team")

            if current_user.id not in {league.commissioner_user_id, current_team.owner_user_id}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not on the clock.")

            now_utc = datetime.now(timezone.utc)
            current_pick_number = existing_picks + 1
            prep_remaining = league_routes._draft_pick_prep_remaining_seconds(
                draft_row=draft_row,
                timer_state=timer_state,
                now_utc=now_utc,
            )
            if prep_remaining > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Next pick begins in {prep_remaining}s.",
                )

            seconds_remaining = league_routes._seconds_remaining_for_current_pick(
                draft_row=draft_row,
                timer_state=timer_state,
                now_utc=now_utc,
                current_team=current_team,
                current_pick_number=current_pick_number,
            )
            if seconds_remaining is not None and seconds_remaining <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Pick clock expired. Auto-pick will submit this turn.",
                )

            player = db.query(Player).filter(Player.id == payload.player_id).with_for_update().first()
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

            slot = assign_draft_roster_slot(db, settings_row, current_team.id, player.position)
            pick = DraftPick(
                draft_id=draft_row.id,
                team_id=current_team.id,
                player_id=player.id,
                made_by_user_id=current_user.id,
                round_number=round_number,
                round_pick=round_pick,
                overall_pick=current_pick_number,
                idempotency_key=resolved_idempotency_key,
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
            league_routes._remove_player_from_draft_queues(
                db,
                draft_id=draft_row.id,
                player_id=player.id,
            )

            league.status = "draft_live"
            league_routes._reset_draft_timer_for_next_pick(
                timer_state=timer_state,
                now_utc=now_utc,
                transition_seconds=0,
                draft_row=draft_row,
            )
            if league_routes.is_draft_complete(current_pick_number, total_picks):
                league_routes._complete_draft(
                    draft_row=draft_row,
                    league=league,
                    timer_state=timer_state,
                    now_utc=now_utc,
                )

            db.add(draft_row)
            db.add(timer_state)
            db.add(league)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if resolved_idempotency_key:
            existing_for_key = (
                db.query(DraftPick)
                .join(Draft, Draft.id == DraftPick.draft_id)
                .filter(
                    Draft.league_id == league.id,
                    DraftPick.idempotency_key == resolved_idempotency_key,
                )
                .first()
            )
            if existing_for_key and existing_for_key.player_id == payload.player_id:
                return get_draft_room_state(db, league, current_user)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_draft_conflict_detail(exc)) from exc

    room = get_draft_room_state(db, league, current_user)
    latest_pick = room.picks[-1] if room.picks else None
    league_routes._emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.pick.made",
        entity_type="draft_pick",
        entity_id=latest_pick.id if latest_pick else None,
        payload={
            "reason": "manual_pick",
            "player_id": payload.player_id,
            "overall_pick": latest_pick.overall_pick if latest_pick else None,
            "team_id": latest_pick.team_id if latest_pick else None,
            "round_number": latest_pick.round_number if latest_pick else None,
            "round_pick": latest_pick.round_pick if latest_pick else None,
            "idempotency_key": resolved_idempotency_key,
        },
    )
    league_routes._emit_draft_event(
        db,
        league_id=league.id,
        event_type="draft.room.updated",
        entity_type="draft_room",
        entity_id=room.draft_room_id,
        payload={"reason": "pick_committed"},
    )
    db.commit()
    return get_draft_room_state(db, league, current_user)


def create_draft_pick(
    db: Session,
    league: League,
    payload: DraftPickCreate,
    current_user: User,
    *,
    idempotency_key: str | None = None,
) -> DraftRoomRead:
    return create_real_draft_pick(
        db,
        league,
        payload,
        current_user,
        idempotency_key=idempotency_key,
    )
