from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PlayerProjectionTrajectoryPointRead(BaseModel):
    week: int = Field(ge=1, le=13)
    points: float | None = Field(default=None, ge=0)
    source: Literal["published", "bye"]
    projection_status: str
    projection_version: str | None = None
    published_at: datetime | None = None


class PlayerValueTrajectoryPointRead(BaseModel):
    week: int = Field(ge=0, le=13)
    value: float = Field(ge=0, le=100)
    source: Literal["preseason", "published"]


class PlayerTrajectoryRead(BaseModel):
    player_id: int
    season: int
    league_id: int | None = None
    projection: list[PlayerProjectionTrajectoryPointRead]
    value: list[PlayerValueTrajectoryPointRead]
    preseason_projection_points: float | None = None
