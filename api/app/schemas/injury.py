from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InjuryHistoryRead(BaseModel):
    id: int
    season: int
    week: int
    status: str
    normalized_status: str = "unknown"
    injury: str | None = None
    body_part: str | None = None
    source: str = "unknown"
    source_updated_at: datetime | None = None
    created_at: datetime


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
    normalized_status: str = "unknown"
    injury: str | None = None
    body_part: str | None = None
    return_timeline: str | None = None
    practice_level: str | None = None
    notes: str | None = None
    source: str = "unknown"
    source_updated_at: datetime | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    cleared_at: datetime | None = None
    last_updated: datetime
    projection_delta: float | None = None
    projection_multiplier: float | None = None
    impact_confidence: float | None = None
    impact_reason: str | None = None
    history: list[InjuryHistoryRead] = Field(default_factory=list)


class InjuryList(BaseModel):
    data: list[InjuryRead]
    total: int
