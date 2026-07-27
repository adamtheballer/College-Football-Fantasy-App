from typing import Literal

from pydantic import BaseModel, Field


class PlayerProjectionTrajectoryPointRead(BaseModel):
    week: int = Field(ge=1, le=13)
    points: float = Field(ge=0)
    source: Literal["published", "modeled", "bye"]


class PlayerValueTrajectoryPointRead(BaseModel):
    week: int = Field(ge=1, le=13)
    value: float = Field(ge=0, le=100)
    source: Literal["published", "modeled"]


class PlayerTrajectoryRead(BaseModel):
    player_id: int
    season: int
    league_id: int | None = None
    projection: list[PlayerProjectionTrajectoryPointRead]
    value: list[PlayerValueTrajectoryPointRead]
