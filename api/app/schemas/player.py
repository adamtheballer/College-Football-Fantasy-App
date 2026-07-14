from datetime import datetime

from pydantic import BaseModel, ConfigDict

from collegefootballfantasy_api.app.schemas.historical_stats import PlayerHistoricalStatsResponse


class PlayerBase(BaseModel):
    external_id: str | None = None
    name: str
    position: str
    school: str
    image_url: str | None = None
    player_class: str | None = None
    sheet_adp: float | None = None
    sheet_projected_season_points: float | None = None
    sheet_projection_stats: dict | None = None
    sheet_source_sheet_id: str | None = None
    sheet_synced_at: datetime | None = None
    cfb27_rank: int | None = None
    cfb27_overall: int | None = None
    cfb27_position_rank: int | None = None
    cfb27_synced_at: datetime | None = None


class PlayerCreate(PlayerBase):
    pass


class PlayerRead(PlayerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_rank: int | None = None
    created_at: datetime
    updated_at: datetime


class PlayerList(BaseModel):
    data: list[PlayerRead]
    total: int
    limit: int
    offset: int


class PlayerCardAboutRead(BaseModel):
    espn_player_id: str | None = None
    height: str | None = None
    weight: str | None = None
    player_class: str | None = None
    birthplace: str | None = None
    status: str | None = None
    jersey: str | None = None
    position: str | None = None
    team: str | None = None
    headshot_url: str | None = None
    source: str = "local"
    message: str | None = None


class PlayerCardInjuryRead(BaseModel):
    id: int
    season: int
    week: int
    status: str
    injury: str | None = None
    return_timeline: str | None = None
    practice_level: str | None = None
    is_game_time_decision: bool = False
    is_returning: bool = False
    notes: str | None = None
    updated_at: datetime


class PlayerCardStatRowRead(BaseModel):
    season: int
    week: int
    source: str
    stats: dict
    updated_at: datetime


class PlayerCardRead(BaseModel):
    player: PlayerRead
    about: PlayerCardAboutRead
    injuries: list[PlayerCardInjuryRead]
    season_stats: list[PlayerCardStatRowRead]
    historical_stats: PlayerHistoricalStatsResponse | None = None
