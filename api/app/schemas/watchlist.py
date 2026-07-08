from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from collegefootballfantasy_api.app.schemas.player import PlayerAvailabilityRead, PlayerRead


class WatchlistCreate(BaseModel):
    name: str
    league_id: int | None = None


class WatchlistUpdate(BaseModel):
    name: str


class WatchlistPlayerCreate(BaseModel):
    player_id: int
    team_id: int | None = None
    notes: str | None = None
    priority: int = 3
    tags: list[str] = Field(default_factory=list)
    alert_available: bool = True
    alert_injury: bool = True
    alert_projection: bool = True
    alert_ownership: bool = True
    alert_matchup: bool = True


class WatchlistPlayerUpdate(BaseModel):
    team_id: int | None = None
    notes: str | None = None
    priority: int | None = None
    tags: list[str] | None = None
    alert_available: bool | None = None
    alert_injury: bool | None = None
    alert_projection: bool | None = None
    alert_ownership: bool | None = None
    alert_matchup: bool | None = None


class WatchlistPlayerRead(BaseModel):
    id: int
    watchlist_id: int
    team_id: int | None = None
    player: PlayerRead
    availability: PlayerAvailabilityRead | None = None
    notes: str | None = None
    priority: int = 3
    tags: list[str] = Field(default_factory=list)
    alert_available: bool = True
    alert_injury: bool = True
    alert_projection: bool = True
    alert_ownership: bool = True
    alert_matchup: bool = True
    created_at: datetime
    updated_at: datetime


class WatchlistRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    league_id: int | None = None
    name: str
    players: list[PlayerRead]
    items: list[WatchlistPlayerRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WatchlistList(BaseModel):
    data: list[WatchlistRead]
    total: int
