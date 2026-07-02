from datetime import datetime, timezone

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


def build_draft_room_state(db: Session, league: League, current_user: User) -> DraftRoomRead:
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
    current_pick = len(picks_rows) + 1
    current_round, current_round_pick, current_team = draft_pick_team_for_number(teams, current_pick)
    if total_picks and len(picks_rows) >= total_picks:
        current_team = None

    user_team = next((team for team in teams if team.owner_user_id == current_user.id), None)
    member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
    league_is_full = member_count >= league.max_teams
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

        member_count = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).count()
        if member_count < league.max_teams:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="draft cannot start until the league is full",
            )

        draft_start = draft_row.draft_datetime_utc
        if draft_start.tzinfo is None:
            draft_start = draft_start.replace(tzinfo=timezone.utc)
        if draft_row.status == "scheduled" and draft_start > datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft has not started yet")

        settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
        if not settings_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")

        teams = ordered_draft_teams(db, league.id)
        if not teams:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no teams available for draft")

        existing_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
        roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
        draft_roster_slots = normalize_roster_slot_limits(roster_slots)
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

        if draft_row.status == "scheduled":
            draft_row.status = "live"
        league.status = "draft_live"
        if total_picks and existing_picks + 1 >= total_picks:
            draft_row.status = "completed"
            league.status = "post_draft"
            finalize_draft_rosters_and_matchups(db, league)

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
