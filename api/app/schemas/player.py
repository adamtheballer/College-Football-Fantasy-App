from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PlayerBase(BaseModel):
    external_id: str | None = None
    name: str
    position: str
    school: str


class PlayerCreate(PlayerBase):
    pass


class PlayerRead(PlayerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PlayerList(BaseModel):
    data: list[PlayerRead]
    total: int
    limit: int
    offset: int
