from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Selection(StrictModel):
    game_id: int | None = Field(None, gt=0)
    team: str | None = Field(None, min_length=1, max_length=200)
    player_id: int | None = Field(None, gt=0)
    slot: Literal["QB", "RB", "WR", "WR1", "WR2", "TE", "FLEX"] | None = None


class Participant(BaseModel):
    user_id: int
    display_name: str
    username: str | None
    avatar_url: str | None
    profile_url: str


class GameRead(BaseModel):
    id: int
    home_team: str
    away_team: str
    start_date: datetime | None
    status: str | None
    home_points: int | None = None
    away_points: int | None = None
