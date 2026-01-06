from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PlayerStatBase(BaseModel):
    player_id: int
    season: int
    week: int
    source: str
    stats: dict[str, Any]


class PlayerStatRead(PlayerStatBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PlayerStatResponse(BaseModel):
    player_id: int
    season: int
    week: int
    source: str
    cached: bool
    stats: dict[str, Any] | None
    message: str | None = None
