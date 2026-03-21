from datetime import datetime

from pydantic import BaseModel, ConfigDict

from collegefootballfantasy_api.app.schemas.player import PlayerRead


class WatchlistCreate(BaseModel):
    name: str
    league_id: int | None = None


class WatchlistUpdate(BaseModel):
    name: str


class WatchlistPlayerCreate(BaseModel):
    player_id: int


class WatchlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    league_id: int | None = None
    name: str
    players: list[PlayerRead]
    created_at: datetime
    updated_at: datetime


class WatchlistList(BaseModel):
    data: list[WatchlistRead]
    total: int
