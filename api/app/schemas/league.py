from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeagueBase(BaseModel):
    name: str
    platform: str
    scoring_type: str


class LeagueCreate(LeagueBase):
    pass


class LeagueUpdate(BaseModel):
    name: str | None = None
    platform: str | None = None
    scoring_type: str | None = None


class LeagueRead(LeagueBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class LeagueList(BaseModel):
    data: list[LeagueRead]
    total: int
    limit: int
    offset: int
