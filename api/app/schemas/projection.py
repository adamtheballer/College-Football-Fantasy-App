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


class ProjectionRead(ProjectionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class ProjectionList(BaseModel):
    data: list[ProjectionRead]
    total: int
    limit: int
    offset: int
