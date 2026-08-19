from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner_name: str | None = Field(default=None, max_length=100)
    owner_avatar_url: str | None = None


class TeamCreate(TeamBase):
    pass


class TeamRead(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    owner_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class TeamList(BaseModel):
    data: list[TeamRead]
    total: int
    limit: int
    offset: int
