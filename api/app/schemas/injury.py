from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InjuryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int
    player_name: str
    team: str
    conference: str | None = None
    position: str
    season: int
    week: int
    status: str
    injury: str | None = None
    return_timeline: str | None = None
    practice_level: str | None = None
    notes: str | None = None
    last_updated: datetime
    projection_delta: float | None = None


class InjuryList(BaseModel):
    data: list[InjuryRead]
    total: int
