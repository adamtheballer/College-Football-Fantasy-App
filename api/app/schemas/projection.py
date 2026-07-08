from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectionBase(BaseModel):
    player_id: int
    season: int
    week: int
    pass_attempts: float
    rush_attempts: float
    targets: float
    receptions: float
    expected_plays: float
    expected_rush_per_play: float
    expected_td_per_play: float
    pass_yards: float
    rush_yards: float
    rec_yards: float
    pass_tds: float
    rush_tds: float
    rec_tds: float
    interceptions: float
    fantasy_points: float
    floor: float
    ceiling: float
    boom_prob: float
    bust_prob: float
    qb_rating: float | None = None
    projection_version: int = 1
    model_version: str = "projection-v1"
    input_snapshot_hash: str | None = None
    generated_at: datetime | None = None
    source_freshness: str = "unknown"
    confidence_score: float = 0.5


class ProjectionRead(ProjectionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    league_fantasy_points: float | None = None
    league_floor: float | None = None
    league_ceiling: float | None = None
    league_breakdown_json: dict | None = None
    scoring_context: str | None = None
    confidence_label: str | None = None
    uncertainty_labels: list[str] = []


class ProjectionList(BaseModel):
    data: list[ProjectionRead]
    total: int
    limit: int
    offset: int


class ProjectionExplanationRead(BaseModel):
    player_id: int
    season: int
    week: int
    model_version: str
    input_snapshot_hash: str | None = None
    generated_at: datetime | None = None
    confidence_score: float
    confidence_label: str
    reasons: list[dict]
    explanation: dict


class ProjectionBacktestRow(BaseModel):
    player_id: int
    player_name: str
    position: str
    team: str
    projected_points: float
    actual_points: float
    error: float
    absolute_error: float
    confidence_score: float


class ProjectionBacktestSummary(BaseModel):
    season: int
    week: int
    league_id: int | None = None
    sample_size: int
    mae: float
    bias: float
    mae_by_position: dict[str, float]
    bias_by_team: dict[str, float]
    bias_by_conference: dict[str, float]
    confidence_calibration: dict[str, dict[str, float]]
    rows: list[ProjectionBacktestRow]
