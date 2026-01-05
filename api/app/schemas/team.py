from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamBase(BaseModel):
    name: str
    owner_name: str | None = None


class TeamCreate(TeamBase):
    pass


class TeamRead(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    created_at: datetime
    updated_at: datetime


class TeamList(BaseModel):
    data: list[TeamRead]
    total: int
    limit: int
    offset: int
