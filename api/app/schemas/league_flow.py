from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeagueBasics(BaseModel):
    name: str
    season_year: int
    max_teams: int
    is_private: bool = True
    description: str | None = None
    icon_url: str | None = None


class LeagueSettingsInput(BaseModel):
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    trade_review_type: str
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool


class DraftScheduleInput(BaseModel):
    draft_datetime_utc: datetime
    timezone: str
    draft_type: str
    pick_timer_seconds: int


class LeagueCreateRequest(BaseModel):
    basics: LeagueBasics
    settings: LeagueSettingsInput
    draft: DraftScheduleInput


class LeagueMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    role: str
    joined_at: datetime


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    league_id: int
    draft_datetime_utc: datetime
    timezone: str
    draft_type: str
    pick_timer_seconds: int
    status: str


class LeagueSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    league_id: int
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    trade_review_type: str
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool


class LeagueSettingsUpdate(BaseModel):
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    trade_review_type: str
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool


class DraftUpdate(BaseModel):
    draft_datetime_utc: datetime
    timezone: str
    draft_type: str
    pick_timer_seconds: int
    status: str = "scheduled"


class LeagueDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    commissioner_user_id: int | None
    season_year: int
    max_teams: int
    is_private: bool
    invite_code: str | None
    description: str | None = None
    icon_url: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    settings: LeagueSettingsRead
    draft: DraftRead | None
    members: list[LeagueMemberRead]


class LeagueCreateResponse(BaseModel):
    league: LeagueDetailRead
    invite_code: str
    invite_link: str


class LeaguePreview(BaseModel):
    id: int
    name: str
    commissioner_name: str | None
    max_teams: int
    member_count: int
    is_private: bool
    draft_datetime_utc: datetime | None
    timezone: str | None
    scoring_preset: str


class JoinByCodeRequest(BaseModel):
    invite_code: str


class JoinLeagueRequest(BaseModel):
    league_id: int


class LeagueMembersList(BaseModel):
    data: list[LeagueMemberRead]
    total: int
