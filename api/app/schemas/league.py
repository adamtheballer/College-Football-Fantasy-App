from datetime import datetime

from pydantic import BaseModel, ConfigDict

from collegefootballfantasy_api.app.schemas.league_flow import LeagueDetailRead


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
    data: list[LeagueDetailRead]
    total: int
    limit: int
    offset: int
