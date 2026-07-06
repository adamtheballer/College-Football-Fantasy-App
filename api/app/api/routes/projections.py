from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_league_or_404, get_optional_current_user, require_league_member
from collegefootballfantasy_api.app.crud.projection import get_projection, list_projections
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.projection_explanation import ProjectionExplanation
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.projection import ProjectionList, ProjectionRead
from collegefootballfantasy_api.app.services.projection_scoring_service import (
    calculate_league_projection_points,
    calculate_league_projection_range,
)
from collegefootballfantasy_api.app.services.projections.explanations import build_projection_reasons

router = APIRouter()


def _league_scoring_json(db: Session, league_id: int, current_user: User | None) -> dict:
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")

    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    return settings.scoring_json if settings else {}


def _projection_read(
    projection: WeeklyProjection,
    scoring_json: dict | None = None,
) -> ProjectionRead:
    row = ProjectionRead.model_validate(projection)
    if scoring_json is None:
        return row

    league_points, breakdown = calculate_league_projection_points(projection, scoring_json)
    league_floor, league_ceiling = calculate_league_projection_range(projection, scoring_json)
    return row.model_copy(
        update={
            "league_fantasy_points": league_points,
            "league_floor": league_floor,
            "league_ceiling": league_ceiling,
            "league_breakdown_json": breakdown,
            "scoring_context": "league",
        }
    )


@router.get("", response_model=ProjectionList)
def list_projections_endpoint(
    season: int,
    week: int,
    league_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> ProjectionList:
    rows, total = list_projections(db, season=season, week=week, limit=limit, offset=offset)
    scoring_json = _league_scoring_json(db, league_id, current_user) if league_id is not None else None
    return ProjectionList(
        data=[_projection_read(row, scoring_json) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{player_id}", response_model=ProjectionRead)
def get_projection_endpoint(
    player_id: int,
    season: int,
    week: int,
    league_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> ProjectionRead:
    row = get_projection(db, player_id=player_id, season=season, week=week)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="projection not found")
    scoring_json = _league_scoring_json(db, league_id, current_user) if league_id is not None else None
    return _projection_read(row, scoring_json)


@router.get("/{player_id}/explanations")
def projection_explanations_endpoint(
    player_id: int,
    season: int,
    week: int,
    db: Session = Depends(get_db),
) -> dict:
    cached = (
        db.query(ProjectionExplanation)
        .filter(
            ProjectionExplanation.player_id == player_id,
            ProjectionExplanation.season == season,
            ProjectionExplanation.week == week,
        )
        .first()
    )
    if cached:
        return {"player_id": player_id, "season": season, "week": week, "reasons": cached.reasons}

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        return {"player_id": player_id, "season": season, "week": week, "reasons": []}

    team_env = (
        db.query(TeamEnvironment)
        .filter(TeamEnvironment.team_name == player.school, TeamEnvironment.season == season, TeamEnvironment.week == week)
        .first()
    )
    usage = (
        db.query(UsageShare)
        .filter(UsageShare.player_id == player_id, UsageShare.season == season, UsageShare.week == week)
        .first()
    )
    injury = (
        db.query(Injury)
        .filter(Injury.player_id == player_id, Injury.season == season, Injury.week == week)
        .first()
    )
    defense = (
        db.query(DefenseRating)
        .filter(DefenseRating.team_name == player.school, DefenseRating.season == season, DefenseRating.week == week)
        .first()
    )

    reasons = build_projection_reasons(
        player.name,
        player.school,
        player.position,
        season,
        week,
        team_env,
        usage,
        injury,
        defense,
    )
    stored = ProjectionExplanation(
        player_id=player_id,
        season=season,
        week=week,
        reasons=reasons,
        model_version="v1",
    )
    db.add(stored)
    db.commit()
    return {"player_id": player_id, "season": season, "week": week, "reasons": reasons}
