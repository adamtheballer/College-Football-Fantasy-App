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

