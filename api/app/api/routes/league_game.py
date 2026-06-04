from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.app.api.deps import (
    get_current_user,
    get_league_or_404,
    require_commissioner,
    require_league_member,
)
from api.app.db.session import get_db
from api.app.models.lineup import Lineup
from api.app.models.matchup import Matchup
from api.app.models.team import Team
from api.app.models.team_weekly_score import TeamWeeklyScore
from api.app.models.fantasy_player_score import FantasyPlayerScore
from api.app.models.player import Player
from api.app.models.user import User
from api.app.schemas.lineup import LineupRead, LineupUpdateRequest, LineupUpdateResponse
from api.app.schemas.scoring import (
    MatchupDetailResponse,
    ScheduleGenerateRequest,
    ScheduleGenerateResponse,
    ScheduleReadResponse,
    WeekFinalizeResponse,
    WeekScoreResponse,
)
from api.app.services import lineup_service, schedule_generator, scoring_service, standings_service

router = APIRouter()


def _team_or_404(db: Session, league_id: int, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team or team.league_id != league_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team not found")
    return team


@router.post("/leagues/{league_id}/schedule/generate", response_model=ScheduleGenerateResponse)
def generate_schedule_endpoint(
    league_id: int,
    payload: ScheduleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScheduleGenerateResponse:
    league, _membership = require_commissioner(db, league_id, current_user)
    rows = schedule_generator.generate_league_schedule(db, league, weeks=payload.weeks)
    return ScheduleGenerateResponse(
        league_id=league.id,
        season=league.season_year,
        created=len(rows),
        matchups=schedule_generator.serialize_matchups(db, rows),
    )


@router.get("/leagues/{league_id}/schedule", response_model=ScheduleReadResponse)
def get_schedule_endpoint(
    league_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScheduleReadResponse:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    rows = schedule_generator.get_league_schedule(db, league)
    return ScheduleReadResponse(
        league_id=league.id,
        season=league.season_year,
        matchups=schedule_generator.serialize_matchups(db, rows),
    )


@router.get("/leagues/{league_id}/teams/{team_id}/lineup", response_model=LineupRead)
def get_lineup_endpoint(
    league_id: int,
    team_id: int,
    season: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LineupRead:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    team = _team_or_404(db, league.id, team_id)
    lineup = lineup_service.get_or_create_lineup(db, league, team, season, week)
    return lineup_service.get_lineup_read_model(db, lineup)


@router.patch("/leagues/{league_id}/teams/{team_id}/lineup", response_model=LineupUpdateResponse)
def update_lineup_endpoint(
    league_id: int,
    team_id: int,
    payload: LineupUpdateRequest,
    season: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LineupUpdateResponse:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    team = _team_or_404(db, league.id, team_id)
    lineup = lineup_service.update_lineup(db, league, team, season, week, payload.assignments, current_user)
    return LineupUpdateResponse(data=lineup_service.get_lineup_read_model(db, lineup))


@router.post("/leagues/{league_id}/teams/{team_id}/lineup/lock", response_model=LineupRead)
def lock_lineup_endpoint(
    league_id: int,
    team_id: int,
    season: int = Query(..., ge=2000, le=2100),
    week: int = Query(..., ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LineupRead:
    league, _membership = require_commissioner(db, league_id, current_user)
    team = _team_or_404(db, league.id, team_id)
    lineup = lineup_service.get_or_create_lineup(db, league, team, season, week)
    locked = lineup_service.lock_lineup(db, lineup)
    return lineup_service.get_lineup_read_model(db, locked)


@router.post("/leagues/{league_id}/weeks/{week}/score", response_model=WeekScoreResponse)
def score_week_endpoint(
    league_id: int,
    week: int,
    season: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeekScoreResponse:
    league, _membership = require_commissioner(db, league_id, current_user)
    return scoring_service.score_league_week(db, league, season or league.season_year, week)


@router.post("/leagues/{league_id}/weeks/{week}/finalize", response_model=WeekFinalizeResponse)
def finalize_week_endpoint(
    league_id: int,
    week: int,
    season: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeekFinalizeResponse:
    league, _membership = require_commissioner(db, league_id, current_user)
    return standings_service.finalize_league_week(db, league, season or league.season_year, week)


@router.get("/leagues/{league_id}/weeks/{week}/scores", response_model=WeekScoreResponse)
def get_week_scores_endpoint(
    league_id: int,
    week: int,
    season: int | None = Query(None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WeekScoreResponse:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    resolved_season = season or league.season_year
    team_rows = (
        db.query(TeamWeeklyScore)
        .filter(
            TeamWeeklyScore.league_id == league.id,
            TeamWeeklyScore.season == resolved_season,
            TeamWeeklyScore.week == week,
        )
        .order_by(TeamWeeklyScore.team_id.asc())
        .all()
    )
    matchup_rows = (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == resolved_season, Matchup.week == week)
        .order_by(Matchup.id.asc())
        .all()
    )
    player_count = (
        db.query(FantasyPlayerScore)
        .filter(
            FantasyPlayerScore.league_id == league.id,
            FantasyPlayerScore.season == resolved_season,
            FantasyPlayerScore.week == week,
        )
        .count()
    )
    return WeekScoreResponse(
        league_id=league.id,
        season=resolved_season,
        week=week,
        player_scores_count=player_count,
        team_scores=scoring_service.serialize_team_scores(db, team_rows),
        matchups=scoring_service.serialize_matchups(db, matchup_rows),
    )


@router.get("/leagues/{league_id}/matchups/{matchup_id}", response_model=MatchupDetailResponse)
def get_matchup_detail_endpoint(
    league_id: int,
    matchup_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MatchupDetailResponse:
    league = get_league_or_404(db, league_id)
    require_league_member(db, league.id, current_user)
    matchup = db.get(Matchup, matchup_id)
    if not matchup or matchup.league_id != league.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="matchup not found")
    home_team = _team_or_404(db, league.id, matchup.home_team_id)
    away_team = _team_or_404(db, league.id, matchup.away_team_id)
    home_lineup = (
        db.query(Lineup)
        .filter(
            Lineup.league_id == league.id,
            Lineup.team_id == home_team.id,
            Lineup.season == matchup.season,
            Lineup.week == matchup.week,
        )
        .first()
    )
    away_lineup = (
        db.query(Lineup)
        .filter(
            Lineup.league_id == league.id,
            Lineup.team_id == away_team.id,
            Lineup.season == matchup.season,
            Lineup.week == matchup.week,
        )
        .first()
    )
    team_scores = (
        db.query(TeamWeeklyScore)
        .filter(
            TeamWeeklyScore.league_id == league.id,
            TeamWeeklyScore.season == matchup.season,
            TeamWeeklyScore.week == matchup.week,
            TeamWeeklyScore.team_id.in_([home_team.id, away_team.id]),
        )
        .all()
    )
    score_by_team = {row.team_id: row for row in team_scores}
    player_rows = (
        db.query(FantasyPlayerScore, Player)
        .join(Player, Player.id == FantasyPlayerScore.player_id)
        .filter(
            FantasyPlayerScore.league_id == league.id,
            FantasyPlayerScore.season == matchup.season,
            FantasyPlayerScore.week == matchup.week,
        )
        .all()
    )
    return MatchupDetailResponse(
        matchup=scoring_service.serialize_matchups(db, [matchup])[0],
        home_lineup=lineup_service.get_lineup_read_model(db, home_lineup) if home_lineup else None,
        away_lineup=lineup_service.get_lineup_read_model(db, away_lineup) if away_lineup else None,
        home_team_score=scoring_service.serialize_team_scores(db, [score_by_team[home_team.id]])[0] if home_team.id in score_by_team else None,
        away_team_score=scoring_service.serialize_team_scores(db, [score_by_team[away_team.id]])[0] if away_team.id in score_by_team else None,
        player_scores=[
            {
                "player_id": score.player_id,
                "player_name": player.name,
                "season": score.season,
                "week": score.week,
                "points": float(score.points or 0.0),
                "breakdown_json": score.breakdown_json or {},
            }
            for score, player in player_rows
        ],
    )
