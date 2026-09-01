from __future__ import annotations

from datetime import date as Date, datetime

from pydantic import BaseModel, Field


class PlayerGameLogStatRead(BaseModel):
    source: str
    stats: dict
    fantasy_points: float | None = None
    updated_at: datetime


class PlayerGameLogSummaryStatRead(BaseModel):
    """One verified season-total field, kept ordered for the player-card UI."""

    label: str
    value: float | int


class PlayerGameLogSeasonSummaryRead(BaseModel):
    """Authoritative totals for the selected season only."""

    teams: list[str] = Field(default_factory=list)
    games_played: int | None = None
    games_started: int | None = None
    stats: list[PlayerGameLogSummaryStatRead] = Field(default_factory=list)
    fantasy_points: float | None = None
    fantasy_points_per_game: float | None = None


class PlayerGameLogRowRead(BaseModel):
    schedule_id: int
    game_id: int | None = None
    team_name: str
    week: int
    date: Date | None = None
    kickoff_at: datetime | None = None
    opponent_name: str | None = None
    location: str
    location_label: str
    neutral_site: bool
    conference_game: bool
    venue: str | None = None
    tv_network: str | None = None
    game_status: str
    stat_status: str
    result: str | None = None
    stats: PlayerGameLogStatRead | None = None


class PlayerGameLogRead(BaseModel):
    player_id: int
    player_name: str
    season: int
    team_name: str | None = None
    position: str
    available_seasons: list[int] = Field(default_factory=list)
    season_summary: PlayerGameLogSeasonSummaryRead | None = None
    games: list[PlayerGameLogRowRead]
    message: str | None = None
