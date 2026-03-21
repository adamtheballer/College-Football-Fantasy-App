from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import generate_invite_code
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
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
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
    LeagueSettingsRead,
    LeagueSettingsUpdate,
    LeagueWorkspaceRead,
    LeagueWorkspaceRosterEntryRead,
    LeagueWorkspaceStandingSummaryRead,
    LeagueWorkspaceTeamRead,
    JoinByCodeRequest,
)

router = APIRouter()

FIXED_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}


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


def _enforce_fixed_roster_settings(payload_settings):
    payload_settings.roster_slots_json = FIXED_ROSTER_SLOTS.copy()
    payload_settings.superflex_enabled = False
    payload_settings.kicker_enabled = True
    payload_settings.defense_enabled = False
    return payload_settings


def _get_league_or_404(db: Session, league_id: int) -> League:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return league


def _get_league_membership(db: Session, league_id: int, user_id: int) -> LeagueMember | None:
    return (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )


def _require_league_member(db: Session, league_id: int, user_id: int) -> LeagueMember:
    membership = _get_league_membership(db, league_id, user_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="league membership required",
        )
    return membership


def _build_allowed_actions(
    league: League, membership: LeagueMember, owned_team: Team | None
) -> list[str]:
    allowed_actions = {
        "open_draft_lobby",
        "view_members",
        "view_standings",
    }
    if owned_team:
        allowed_actions.update({"view_roster", "manage_roster", "manage_team"})
    if membership.role == "commissioner" or league.commissioner_user_id == membership.user_id:
        allowed_actions.update(
            {"update_settings", "regenerate_invite", "reschedule_draft", "delete_league"}
        )
    return sorted(allowed_actions)


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
    membership = _require_league_member(db, league.id, current_user.id)
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


def _league_workspace(
    db: Session,
    league: League,
    membership: LeagueMember,
    current_user: User,
) -> LeagueWorkspaceRead:
    owned_team = (
        db.query(Team)
        .filter(Team.league_id == league.id, Team.owner_user_id == current_user.id)
        .first()
    )
    roster_entries = []
    if owned_team:
        roster_rows = (
            db.query(RosterEntry)
            .filter(RosterEntry.team_id == owned_team.id)
            .all()
        )
        roster_entries = [
            LeagueWorkspaceRosterEntryRead(
                id=row.id,
                team_id=row.team_id,
                player_id=row.player_id,
                slot=row.slot,
                status=row.status,
                player_name=row.player.name if row.player else None,
                player_school=row.player.school if row.player else None,
                player_position=row.player.position if row.player else None,
            )
            for row in roster_rows
        ]

    teams = db.query(Team).filter(Team.league_id == league.id).all()
    roster_counts = dict(
        db.query(RosterEntry.team_id, func.count(RosterEntry.id))
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league.id)
        .group_by(RosterEntry.team_id)
        .all()
    )
    sorted_teams = sorted(
        teams,
        key=lambda team: (-roster_counts.get(team.id, 0), team.created_at, team.id),
    )
    standings_summary = [
        LeagueWorkspaceStandingSummaryRead(
            team_id=team.id,
            team_name=team.name,
            wins=0,
            losses=0,
            ties=0,
            points_for=None,
            rank=index,
        )
        for index, team in enumerate(sorted_teams, start=1)
    ]

    return LeagueWorkspaceRead(
        league=_league_detail(db, league),
        membership=LeagueMemberRead.model_validate(membership),
        owned_team=(
            LeagueWorkspaceTeamRead(
                id=owned_team.id,
                league_id=owned_team.league_id,
                name=owned_team.name,
                owner_user_id=owned_team.owner_user_id,
            )
            if owned_team
            else None
        ),
        roster=roster_entries,
        matchup_summary=None,
        standings_summary=standings_summary,
        allowed_actions=_build_allowed_actions(league, membership, owned_team),
    )


@router.post("/create", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_flow(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueCreateResponse:
    payload.settings = _enforce_fixed_roster_settings(payload.settings)
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
    league = _get_league_or_404(db, league_id)
    return _league_detail(db, league)


@router.get("/{league_id}/workspace", response_model=LeagueWorkspaceRead)
def get_league_workspace_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWorkspaceRead:
    league = _get_league_or_404(db, league_id)
    membership = _require_league_member(db, league.id, current_user.id)
    return _league_workspace(db, league, membership, current_user)


@router.get("/{league_id}/draft-room", response_model=DraftRoomRead)
def get_draft_room_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = _get_league_or_404(db, league_id)
    return _draft_room_state(db, league, current_user)


@router.post("/{league_id}/draft-picks", response_model=DraftRoomRead, status_code=status.HTTP_201_CREATED)
def create_draft_pick_endpoint(
    league_id: int,
    payload: DraftPickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = _get_league_or_404(db, league_id)
    _require_league_member(db, league.id, current_user.id)
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
    payload = _enforce_fixed_roster_settings(payload)
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
