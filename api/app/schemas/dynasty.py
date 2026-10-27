from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class DynastyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    season: int = Field(ge=2027, le=2097)
    team_count: int = Field(ge=2, le=24)
    roster_limit: int = Field(ge=2, le=100)
    startup_rounds: int = Field(ge=1, le=100)
    freshman_rounds: int = Field(ge=1, le=20)
    future_pick_years: int = Field(default=2, ge=1, le=3)

    @model_validator(mode="after")
    def roster_capacity(self):
        if max(self.startup_rounds, self.freshman_rounds) > self.roster_limit:
            raise ValueError("draft rounds cannot exceed roster capacity")
        return self


class DynastyJoin(BaseModel):
    invite_code: str = Field(min_length=1, max_length=30)
    team_name: str = Field(min_length=1, max_length=80)


class DynastyCatalogFact(BaseModel):
    player_id: int = Field(gt=0)
    season: int = Field(ge=2027, le=2100)
    entry_season: int = Field(ge=2000, le=2100)
    school: str = Field(min_length=1, max_length=200)
    academic_class: Literal[
        "FR", "RSFR", "SO", "RSSO", "JR", "RSJR", "SR", "RSSR", "GR", "UNKNOWN"
    ]
    birth_date: date | None = None
    eligible: bool
    source_url: HttpUrl = Field(max_length=1000)
    base_value: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def dates(self):
        if self.entry_season > self.season or (
            self.birth_date and self.birth_date >= date(self.season, 8, 1)
        ):
            raise ValueError("invalid college entry or birth date")
        if self.source_url.scheme != "https":
            raise ValueError("reviewed evidence must use HTTPS")
        return self


class DynastyCatalogInput(BaseModel):
    data: list[DynastyCatalogFact] = Field(min_length=1, max_length=200)


class DynastySelection(BaseModel):
    player_id: int = Field(gt=0)


class DynastyAsset(BaseModel):
    kind: Literal["player", "pick"]
    id: int = Field(gt=0)


class DynastyTradeCreate(BaseModel):
    from_team_id: int = Field(gt=0)
    to_team_id: int = Field(gt=0)
    give: list[DynastyAsset] = Field(min_length=1, max_length=20)
    receive: list[DynastyAsset] = Field(min_length=1, max_length=20)


class DynastyFinish(BaseModel):
    team_id: int = Field(gt=0)
    wins: int = Field(ge=0)
    losses: int = Field(ge=0)
    ties: int = Field(default=0, ge=0)
    points_for: float = Field(ge=0, allow_inf_nan=False)
    playoff_finish: int | None = Field(default=None, ge=1, le=24)


class DynastyClose(BaseModel):
    results: list[DynastyFinish] = Field(min_length=2, max_length=24)


class DynastyValue(BaseModel):
    policy_version: str = "dynasty_preview_v1"
    provisional: bool = True
    base_value: float | None
    academic_class: str
    class_factor: float
    age: int | None
    age_factor: float
    estimate: float | None


class DynastyPoolPlayer(BaseModel):
    player_id: int
    name: str
    school: str
    position: str
    entry_season: int
    source_url: str
    value: DynastyValue


class DynastyPool(BaseModel):
    data: list[DynastyPoolPlayer]
    total: int
    limit: int
    offset: int


class DynastyPickRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    season: int
    round_number: int
    original_team_id: int
    owner_team_id: int
    overall_pick: int | None
    player_id: int | None


class DynastyTeamRead(BaseModel):
    id: int
    name: str
    owner_user_id: int | None


class DynastyRosterRead(BaseModel):
    id: int
    team_id: int
    player_id: int
    name: str
    position: str
    school: str | None
    value: DynastyValue | None


class DynastyTradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_team_id: int
    to_team_id: int
    status: str
    assets_json: list[dict]


class DynastyState(BaseModel):
    league_id: int
    name: str
    commissioner_user_id: int | None
    invite_code: str | None
    startup_season: int
    current_season: int
    roster_limit: int
    startup_rounds: int
    freshman_rounds: int
    future_pick_years: int
    draft_kind: str
    status: str
    pick_cursor: int
    order: list[int]
    next_pick_id: int | None
    teams: list[DynastyTeamRead]
    rosters: list[DynastyRosterRead]
    picks: list[DynastyPickRead]
    trades: list[DynastyTradeRead]
    departures: list[dict]


class DynastyList(BaseModel):
    data: list[DynastyState]
