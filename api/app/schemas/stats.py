from datetime import datetime

from pydantic import BaseModel


class TeamStatsSummary(BaseModel):
    team: str
    conference: str
    bye_week: int | None = None
    has_offense_data: bool = False
    has_defense_data: bool = False
    has_advanced_data: bool = False
    updated_at: datetime | None = None


class TeamStatsSummaryList(BaseModel):
    data: list[TeamStatsSummary]
    total: int


class TeamStatsDetail(BaseModel):
    team: str
    conference: str
    season: int
    week: int
    bye_week: int | None = None
    offense: dict[str, float | str | int | None] = {}
    defense: dict[str, float | str | int | None] = {}
    advanced: dict[str, float | str | int | None | dict | list] = {}
    last_updated: datetime | None = None


class TeamStandingRow(BaseModel):
    team: str
    conference: str
    conference_rank: int | None = None
    conference_wins: int | None = None
    conference_losses: int | None = None
    overall_wins: int | None = None
    overall_losses: int | None = None


class TeamStandingsList(BaseModel):
    data: list[TeamStandingRow]
    total: int


class TeamInjuryRow(BaseModel):
    player_id: int
    player_name: str
    team: str
    conference: str
    position: str
    status: str
    injury: str | None = None
    return_timeline: str | None = None
    practice_level: str | None = None
    notes: str | None = None
    last_updated: datetime
    projection_delta: float | None = None


class TeamInjuriesList(BaseModel):
    data: list[TeamInjuryRow]
    total: int
