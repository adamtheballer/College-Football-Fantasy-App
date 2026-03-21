from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    get_league_or_404,
    require_commissioner,
    require_league_member,
)
from collegefootballfantasy_api.app.crud.league import delete_league, list_leagues
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
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
    LeagueSettingsUpdate,
    LeagueWorkspaceRead,
    JoinByCodeRequest,
)
from collegefootballfantasy_api.app.services.league_flow import (
    FIXED_ROSTER_SLOTS,
    create_league,
    join_league as join_league_flow,
    regenerate_invite as regenerate_invite_flow,
    reschedule_draft as reschedule_draft_flow,
    update_league_settings as update_league_settings_flow,
)
from collegefootballfantasy_api.app.services.league_workspace import (
    build_league_workspace,
    get_league_detail,
)

router = APIRouter()


def _ordered_draft_teams(db: Session, league_id: int) -> list[Team]:
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    return sorted(teams, key=lambda team: (team.created_at, team.id))


def _draft_pick_team_for_number(teams: list[Team], pick_number: int) -> tuple[int, int, Team | None]:
    if not teams:
        return 1, 1, None
    total_teams = len(teams)
    round_number = ((pick_number - 1) // total_teams) + 1
    round_pick = ((pick_number - 1) % total_teams) + 1
    ordered_teams = teams if round_number % 2 == 1 else list(reversed(teams))
    return round_number, round_pick, ordered_teams[round_pick - 1]


def _assign_roster_slot(
    db: Session,
    settings_row: LeagueSettings,
    team_id: int,
    player_position: str,
) -> str:
    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    current_counts = dict(
        db.query(RosterEntry.slot, func.count(RosterEntry.id))
        .filter(RosterEntry.team_id == team_id)
        .group_by(RosterEntry.slot)
        .all()
    )

    primary_limit = int(roster_slots.get(player_position, 0))
    if primary_limit and current_counts.get(player_position, 0) < primary_limit:
        return player_position

    if settings_row.superflex_enabled:
        superflex_limit = int(roster_slots.get("SUPERFLEX", 0))
        if player_position == "QB" and current_counts.get("SUPERFLEX", 0) < superflex_limit:
            return "SUPERFLEX"

    bench_limit = int(roster_slots.get("BENCH", 0))
    if current_counts.get("BENCH", 0) < bench_limit:
        return "BENCH"

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team roster is full")


def _draft_room_state(db: Session, league: League, current_user: User) -> DraftRoomRead:
    membership = require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")

    teams = _ordered_draft_teams(db, league.id)
    picks_rows = (
        db.query(DraftPick, Team, Player)
        .join(Team, Team.id == DraftPick.team_id)
        .join(Player, Player.id == DraftPick.player_id)
        .filter(DraftPick.draft_id == draft_row.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )

    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    total_picks = sum(int(value) for value in roster_slots.values()) * len(teams)
    current_pick = len(picks_rows) + 1
    current_round, current_round_pick, current_team = _draft_pick_team_for_number(teams, current_pick)
    if total_picks and len(picks_rows) >= total_picks:
        current_team = None

    user_team = next((team for team in teams if team.owner_user_id == current_user.id), None)
    can_make_pick = bool(
        current_team
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
@router.post("", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_endpoint(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    return create_league(payload, db, current_user)


@router.post("/create", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_flow(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    return create_league(payload, db, current_user)


@router.get("", response_model=LeagueList)
def list_leagues_endpoint(
    limit: int = 50,
    offset: int = 0,
    scope: str = "member",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueList:
    leagues, total = list_leagues(
        db,
        limit=limit,
        offset=offset,
        user_id=current_user.id,
        scope=scope,
    )
    return LeagueList(
        data=[get_league_detail(db, league) for league in leagues],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{league_id}", response_model=LeagueDetailRead)
def get_league_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league_id, current_user)
    return get_league_detail(db, league)


@router.get("/{league_id}/workspace", response_model=LeagueWorkspaceRead)
def get_league_workspace_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWorkspaceRead:
    league = get_league_or_404(db, league_id)
    membership = require_league_member(db, league.id, current_user)
    return build_league_workspace(db, league, membership, current_user)


@router.get("/{league_id}/draft-room", response_model=DraftRoomRead)
def get_draft_room_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    return _draft_room_state(db, league, current_user)


@router.post("/{league_id}/draft-picks", response_model=DraftRoomRead, status_code=status.HTTP_201_CREATED)
def create_draft_pick_endpoint(
    league_id: int,
    payload: DraftPickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    if not draft_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")

    teams = _ordered_draft_teams(db, league.id)
    if not teams:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no teams available for draft")

    existing_picks = db.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count()
    roster_slots = settings_row.roster_slots_json or FIXED_ROSTER_SLOTS
    total_picks = sum(int(value) for value in roster_slots.values()) * len(teams)
    if total_picks and existing_picks >= total_picks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="draft is complete")

    round_number, round_pick, current_team = _draft_pick_team_for_number(teams, existing_picks + 1)
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

    slot = _assign_roster_slot(db, settings_row, current_team.id, player.position)
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

    if draft_row.status == "scheduled":
        draft_row.status = "live"
    league.status = "draft_live"
    if total_picks and existing_picks + 1 >= total_picks:
        draft_row.status = "completed"
        league.status = "post_draft"

    db.add(draft_row)
    db.add(league)
    db.commit()
    return _draft_room_state(db, league, current_user)


@router.get("/{league_id}/members", response_model=LeagueMembersList)
def list_league_members(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMembersList:
    require_league_member(db, league_id, current_user)
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
    return join_league_flow(db, league, current_user)


@router.post("/{league_id}/regenerate-invite", response_model=LeagueCreateResponse)
def regenerate_invite(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    league, _ = require_commissioner(db, league_id, current_user)
    return regenerate_invite_flow(db, league, current_user)


@router.patch("/{league_id}/settings", response_model=LeagueDetailRead)
def update_league_settings(
    league_id: int,
    payload: LeagueSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueDetailRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return update_league_settings_flow(db, league, payload)


@router.patch("/{league_id}/draft", response_model=DraftRead)
def reschedule_draft(
    league_id: int,
    payload: DraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return reschedule_draft_flow(db, league, payload)


@router.delete("/{league_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_league_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    league, _ = require_commissioner(db, league_id, current_user)
    delete_league(db, league)
