from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import (
    get_current_user,
    get_league_or_404,
    require_commissioner,
    require_league_member,
    require_verified_user,
)
from collegefootballfantasy_api.app.crud.league import delete_league, list_leagues
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.draft_room import (
    DraftPickCreate,
    DraftRoomRead,
)
from collegefootballfantasy_api.app.schemas.league import LeagueList
from collegefootballfantasy_api.app.schemas.league_flow import (
    DraftRead,
    DraftUpdate,
    LeagueCreateRequest,
    LeagueCreateResponse,
    LeagueDetailRead,
    LeagueMatchupTabRead,
    LeagueNewsList,
    LeagueMemberRead,
    LeagueMembersList,
    LeaguePowerRankingList,
    LeaguePreview,
    LeagueRosterTabRead,
    LeagueScoreboardList,
    LeagueScoreRecalculateResponse,
    LeagueSettingsViewRead,
    LeagueSettingsUpdate,
    LeagueWorkspaceRead,
    JoinByCodeRequest,
)
from collegefootballfantasy_api.app.services.draft_service import (
    build_draft_room_state,
    create_real_draft_pick,
    start_draft,
)
from collegefootballfantasy_api.app.services.league_flow import (
    create_league,
    join_league as join_league_flow,
    regenerate_invite as regenerate_invite_flow,
    revoke_invite as revoke_invite_flow,
    reschedule_draft as reschedule_draft_flow,
    update_league_settings as update_league_settings_flow,
)
from collegefootballfantasy_api.app.services.league_workspace import (
    build_league_news_items,
    build_power_rankings_rows,
    build_scoreboard_rows,
    build_league_workspace,
    get_league_detail,
)
from collegefootballfantasy_api.app.services.league_roster_matchup import (
    build_matchup_tab_view,
    build_roster_tab_view,
    build_settings_view,
)
from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation

router = APIRouter()
@router.post("", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_endpoint(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> LeagueCreateResponse:
    return create_league(payload, db, current_user)


@router.post("/create", response_model=LeagueCreateResponse, status_code=status.HTTP_201_CREATED)
def create_league_flow(
    payload: LeagueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
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
        data=[get_league_detail(db, league, viewer=current_user) for league in leagues],
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
    return get_league_detail(db, league, viewer=current_user)


@router.get("/{league_id}/workspace", response_model=LeagueWorkspaceRead)
def get_league_workspace_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueWorkspaceRead:
    league = get_league_or_404(db, league_id)
    membership = require_league_member(db, league.id, current_user)
    return build_league_workspace(db, league, membership, current_user)


@router.get("/{league_id}/roster", response_model=LeagueRosterTabRead)
def get_league_roster_tab_endpoint(
    league_id: int,
    week: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueRosterTabRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return build_roster_tab_view(db, league, current_user, selected_week=week)


@router.get("/{league_id}/matchup", response_model=LeagueMatchupTabRead)
def get_league_matchup_tab_endpoint(
    league_id: int,
    week: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueMatchupTabRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return build_matchup_tab_view(db, league, current_user, selected_week=week)


@router.get("/{league_id}/settings-view", response_model=LeagueSettingsViewRead)
def get_league_settings_tab_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueSettingsViewRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return build_settings_view(db, league, current_user)


@router.get("/{league_id}/matchups", response_model=LeagueScoreboardList)
def get_league_matchups_endpoint(
    league_id: int,
    week: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueScoreboardList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows = build_scoreboard_rows(db, league, week=week)
    return LeagueScoreboardList(data=rows, total=len(rows))


@router.post("/{league_id}/weeks/{week}/recalculate-scores", response_model=LeagueScoreRecalculateResponse)
def recalculate_league_week_scores_endpoint(
    league_id: int,
    week: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> LeagueScoreRecalculateResponse:
    league, _ = require_commissioner(db, league_id, current_user)
    summary = run_league_scoring_recalculation(
        db,
        league_id=league.id,
        season=league.season_year,
        week=week,
        provider="manual",
    )
    return LeagueScoreRecalculateResponse(
        league_id=league.id,
        season=league.season_year,
        week=week,
        players_scored=summary.players_scored,
        teams_scored=summary.teams_scored,
        matchups_updated=summary.matchups_updated,
        standings_updated=summary.standings_updated,
    )


@router.get("/{league_id}/power-rankings", response_model=LeaguePowerRankingList)
def get_league_power_rankings_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeaguePowerRankingList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows = build_power_rankings_rows(db, league)
    return LeaguePowerRankingList(data=rows, total=len(rows))


@router.get("/{league_id}/news", response_model=LeagueNewsList)
def get_league_news_endpoint(
    league_id: int,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeagueNewsList:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows = build_league_news_items(db, league, limit=max(1, min(limit, 100)))
    return LeagueNewsList(data=rows, total=len(rows), limit=max(1, min(limit, 100)))


@router.get("/{league_id}/draft-room", response_model=DraftRoomRead)
def get_draft_room_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return build_draft_room_state(db, league, current_user)


@router.post("/{league_id}/draft/start", response_model=DraftRoomRead)
def start_draft_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> DraftRoomRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return start_draft(db, league=league, current_user=current_user)


@router.post("/{league_id}/draft-picks", response_model=DraftRoomRead, status_code=status.HTTP_201_CREATED)
def create_draft_pick_endpoint(
    league_id: int,
    payload: DraftPickCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> DraftRoomRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    return create_real_draft_pick(db, league=league, payload=payload, current_user=current_user)


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
    current_user: User = Depends(require_verified_user),
) -> LeagueDetailRead:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return join_league_flow(db, league, current_user)


@router.post("/{league_id}/regenerate-invite", response_model=LeagueCreateResponse)
def regenerate_invite(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> LeagueCreateResponse:
    league, _ = require_commissioner(db, league_id, current_user)
    return regenerate_invite_flow(db, league, current_user)


@router.post("/{league_id}/invite/rotate", response_model=LeagueCreateResponse)
def rotate_invite(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> LeagueCreateResponse:
    league, _ = require_commissioner(db, league_id, current_user)
    return regenerate_invite_flow(db, league, current_user)


@router.post("/{league_id}/invite/revoke", response_model=LeagueDetailRead)
def revoke_invite(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> LeagueDetailRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return revoke_invite_flow(db, league, current_user)


@router.patch("/{league_id}/settings", response_model=LeagueDetailRead)
def update_league_settings(
    league_id: int,
    payload: LeagueSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> LeagueDetailRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return update_league_settings_flow(db, league, payload, current_user)


@router.patch("/{league_id}/draft", response_model=DraftRead)
def reschedule_draft(
    league_id: int,
    payload: DraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> DraftRead:
    league, _ = require_commissioner(db, league_id, current_user)
    return reschedule_draft_flow(db, league, payload)


@router.delete("/{league_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_league_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_verified_user),
) -> None:
    league, _ = require_commissioner(db, league_id, current_user)
    delete_league(db, league)
