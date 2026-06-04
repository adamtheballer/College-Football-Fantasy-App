from pydantic import BaseModel

from api.app.schemas.lineup import LineupRead


class FantasyPlayerScoreRead(BaseModel):
    player_id: int
    player_name: str | None = None
    season: int
    week: int
    points: float
    breakdown_json: dict


class TeamWeeklyScoreRead(BaseModel):
    team_id: int
    team_name: str | None = None
    season: int
    week: int
    starter_points: float
    bench_points: float
    total_points: float
    breakdown_json: dict


class MatchupScoreRead(BaseModel):
    matchup_id: int
    week: int
    status: str
    home_team_id: int
    home_team_name: str | None = None
    home_score: float
    away_team_id: int
    away_team_name: str | None = None
    away_score: float


class ScheduleGenerateRequest(BaseModel):
    weeks: int = 12


class ScheduleGenerateResponse(BaseModel):
    league_id: int
    season: int
    created: int
    matchups: list[MatchupScoreRead]


class ScheduleReadResponse(BaseModel):
    league_id: int
    season: int
    matchups: list[MatchupScoreRead]


class WeekScoreResponse(BaseModel):
    league_id: int
    season: int
    week: int
    player_scores_count: int
    team_scores: list[TeamWeeklyScoreRead]
    matchups: list[MatchupScoreRead]


class WeekFinalizeStandingRead(BaseModel):
    team_id: int
    team_name: str | None = None
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float


class WeekFinalizeResponse(BaseModel):
    league_id: int
    season: int
    week: int
    finalized_matchups: int
    standings: list[WeekFinalizeStandingRead]


class MatchupDetailResponse(BaseModel):
    matchup: MatchupScoreRead
    home_lineup: LineupRead | None = None
    away_lineup: LineupRead | None = None
    home_team_score: TeamWeeklyScoreRead | None = None
    away_team_score: TeamWeeklyScoreRead | None = None
    player_scores: list[FantasyPlayerScoreRead]
