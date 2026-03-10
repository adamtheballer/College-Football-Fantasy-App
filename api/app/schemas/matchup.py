from pydantic import BaseModel, ConfigDict


class MatchupGradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team: str
    season: int
    week: int
    position: str
    grade: str
    rank: int
    yards_per_target: float
    yards_per_rush: float
    pass_td_rate: float
    rush_td_rate: float
    explosive_rate: float
    pressure_rate: float


class MatchupGradeList(BaseModel):
    data: list[MatchupGradeRead]
    total: int
