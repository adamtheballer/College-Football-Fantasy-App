from __future__ import annotations

from datetime import date as Date, datetime

from pydantic import BaseModel


class PlayerGameLogStatRead(BaseModel):
    source: str
    stats: dict
    fantasy_points: float | None = None
    updated_at: datetime


class PlayerGameLogRowRead(BaseModel):
    schedule_id: int
    game_id: int | None = None
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


class PlayerGameLogSeasonSummaryRead(BaseModel):
    """Verified standard-scoring total shown before the individual game rows."""

    season: int
    fantasy_points: float
    finalized_games: int
    source: str = "verified_player_stats"


class PlayerGameLogRead(BaseModel):
    player_id: int
    player_name: str
    season: int
    team_name: str | None = None
    position: str
    games: list[PlayerGameLogRowRead]
    season_summary: PlayerGameLogSeasonSummaryRead | None = None
    message: str | None = None
