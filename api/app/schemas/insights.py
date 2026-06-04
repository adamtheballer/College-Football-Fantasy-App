from pydantic import BaseModel


class AccoladesResponse(BaseModel):
    user_id: int
    first_name: str
    time_on_app_hours: float
    trades_sent: int
    matchups_won: int
    matchups_played: int
    global_rank: int | None = None
    global_percentile: float | None = None


class DynastyCareerResponse(BaseModel):
    user_id: int
    championships: int
    win_pct: float
    trades_completed: int
    total_points_scored: float
    years_played: int
    dynasty_power_rating: float


class RivalryRow(BaseModel):
    rival_user_id: int
    rival_name: str
    record_wins: int
    record_losses: int
    total_points_for: float
    total_points_against: float
    matchup_count: int
    trash_talk_score: int


class RivalryList(BaseModel):
    data: list[RivalryRow]
    total: int


class UserAnalyticsRow(BaseModel):
    user_id: int
    name: str
    championships: int
    win_pct: float
    total_points: float
    trades_completed: int
    dynasty_power_rating: float


class UserAnalyticsList(BaseModel):
    data: list[UserAnalyticsRow]
    total: int


class PlayerCompareRequest(BaseModel):
    player_a_id: int
    player_b_id: int
    season: int
    week: int = 1


class PlayerCompareSide(BaseModel):
    player_id: int
    player_name: str
    school: str
    position: str
    fantasy_ppg: float
    usage_rate: float
    red_zone_touches: float
    projected_matchup_difficulty: str


class PlayerCompareResponse(BaseModel):
    player_a: PlayerCompareSide
    player_b: PlayerCompareSide

