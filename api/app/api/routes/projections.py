from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404, require_league_member
from collegefootballfantasy_api.app.crud.projection import get_projection, list_projections
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.projection_explanation import ProjectionExplanation
from collegefootballfantasy_api.app.models.projection_input_audit import ProjectionInputAudit
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.projection import (
    ProjectionBacktestSummary,
    ProjectionExplanationRead,
    ProjectionList,
    ProjectionRead,
)
from collegefootballfantasy_api.app.services.projection_scoring_service import (
    calculate_league_projection_points,
    calculate_league_projection_range,
)
from collegefootballfantasy_api.app.services.projections.backtesting import build_projection_backtest
from collegefootballfantasy_api.app.services.projections.confidence import confidence_label, uncertainty_labels
from collegefootballfantasy_api.app.services.projections.explanations import (
    build_projection_explanation_contract,
    build_projection_reasons,
)
from collegefootballfantasy_api.app.services.projections.snapshots import stable_snapshot_hash

router = APIRouter()


def _league_scoring_json(db: Session, league_id: int, authorization: str | None) -> dict:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")

    current_user = get_current_user(db, authorization)
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    return settings.scoring_json if settings else {}


def _projection_read(
    projection: WeeklyProjection,
    scoring_json: dict | None = None,
) -> ProjectionRead:
    row = ProjectionRead.model_validate(projection).model_copy(
        update={
            "confidence_label": confidence_label(projection.confidence_score),
            "uncertainty_labels": uncertainty_labels(
                confidence_score=projection.confidence_score,
                source_freshness=projection.source_freshness,
            ),
        }
    )
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
            "confidence_label": confidence_label(projection.confidence_score),
            "uncertainty_labels": uncertainty_labels(
                confidence_score=projection.confidence_score,
                source_freshness=projection.source_freshness,
            ),
        }
    )


def _projection_snapshot_hash(projection: WeeklyProjection) -> str:
    if projection.input_snapshot_hash:
        return projection.input_snapshot_hash
    return stable_snapshot_hash(
        {
            "player_id": projection.player_id,
            "season": projection.season,
            "week": projection.week,
            "fantasy_points": projection.fantasy_points,
            "floor": projection.floor,
            "ceiling": projection.ceiling,
            "model_version": projection.model_version,
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
    authorization: str | None = Header(default=None),
) -> ProjectionList:
    rows, total = list_projections(db, season=season, week=week, limit=limit, offset=offset)
    scoring_json = _league_scoring_json(db, league_id, authorization) if league_id is not None else None
    return ProjectionList(
        data=[_projection_read(row, scoring_json) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/backtest", response_model=ProjectionBacktestSummary)
def projection_backtest_endpoint(
    season: int,
    week: int,
    league_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> ProjectionBacktestSummary:
    if league_id is not None:
        _league_scoring_json(db, league_id, authorization)
    return build_projection_backtest(db, season=season, week=week, league_id=league_id, limit=limit)


@router.get("/{player_id}", response_model=ProjectionRead)
def get_projection_endpoint(
    player_id: int,
    season: int,
    week: int,
    league_id: int | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> ProjectionRead:
    row = get_projection(db, player_id=player_id, season=season, week=week)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="projection not found")
    scoring_json = _league_scoring_json(db, league_id, authorization) if league_id is not None else None
    return _projection_read(row, scoring_json)


@router.get("/{player_id}/explanations", response_model=ProjectionExplanationRead)
def projection_explanations_endpoint(
    player_id: int,
    season: int,
    week: int,
    db: Session = Depends(get_db),
) -> ProjectionExplanationRead:
    projection = get_projection(db, player_id=player_id, season=season, week=week)
    if not projection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="projection not found")
    input_hash = _projection_snapshot_hash(projection)
    cached = (
        db.query(ProjectionExplanation)
        .filter(
            ProjectionExplanation.player_id == player_id,
            ProjectionExplanation.season == season,
            ProjectionExplanation.week == week,
        )
        .first()
    )
    if cached and cached.input_snapshot_hash == input_hash and cached.explanation:
        return ProjectionExplanationRead(
            player_id=player_id,
            season=season,
            week=week,
            model_version=cached.model_version,
            input_snapshot_hash=cached.input_snapshot_hash,
            generated_at=cached.generated_at,
            confidence_score=cached.confidence_score,
            confidence_label=confidence_label(cached.confidence_score),
            reasons=cached.reasons,
            explanation=cached.explanation,
        )

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

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
    explanation = build_projection_explanation_contract(
        projection=projection,
        player_name=player.name,
        team=player.school,
        position=player.position,
        team_env=team_env,
        usage=usage,
        injury=injury,
        defense=defense,
    )
    generated_at = datetime.now(timezone.utc)
    if not cached:
        cached = ProjectionExplanation(player_id=player_id, season=season, week=week, reasons=[])
    cached.reasons = reasons
    cached.model_version = projection.model_version
    cached.input_snapshot_hash = input_hash
    cached.explanation = explanation
    cached.confidence_score = projection.confidence_score
    cached.generated_at = generated_at
    db.add(cached)

    audit = (
        db.query(ProjectionInputAudit)
        .filter(
            ProjectionInputAudit.player_id == player_id,
            ProjectionInputAudit.season == season,
            ProjectionInputAudit.week == week,
        )
        .first()
    )
    if not audit:
        audit = ProjectionInputAudit(player_id=player_id, season=season, week=week, inputs={})
    audit.model_version = projection.model_version
    audit.input_snapshot_hash = input_hash
    audit.generated_at = generated_at
    audit.source_freshness = {
        "projection": projection.source_freshness,
        "injury_updated_at": injury.updated_at.isoformat() if injury else None,
        "team_environment_updated_at": team_env.updated_at.isoformat() if team_env else None,
        "usage_updated_at": usage.updated_at.isoformat() if usage else None,
    }
    audit.inputs = {
        "projection_id": projection.id,
        "player_id": player.id,
        "team_environment_id": team_env.id if team_env else None,
        "usage_id": usage.id if usage else None,
        "injury_id": injury.id if injury else None,
        "defense_rating_id": defense.id if defense else None,
    }
    db.add(audit)
    db.commit()
    return ProjectionExplanationRead(
        player_id=player_id,
        season=season,
        week=week,
        model_version=cached.model_version,
        input_snapshot_hash=cached.input_snapshot_hash,
        generated_at=cached.generated_at,
        confidence_score=cached.confidence_score,
        confidence_label=confidence_label(cached.confidence_score),
        reasons=cached.reasons,
        explanation=cached.explanation or {},
    )
