from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
