from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


HistoricalStatsStatus = Literal[
    "available",
    "not_available",
    "disabled",
    "no_provider_mapping",
    "provider_unavailable",
]


class HistoricalStatValue(BaseModel):
    label: str
    value: float | int | str | None


class HistoricalStatsCategory(BaseModel):
    key: str
    label: str
    stats: list[HistoricalStatValue]


class HistoricalStatsFreshness(BaseModel):
    provider: str
    provider_player_id: str | None = None
    imported_at: datetime | None = None
    provider_updated_at: datetime | None = None
    parser_version: str | None = None
    source_response_hash: str | None = None
    is_final: bool = False


class HistoricalStatsScoringContext(BaseModel):
    scoring_rules_version: str | None = None
    fantasy_points: float | None = None
    fantasy_points_per_game: float | None = None


class PlayerHistoricalSeasonRead(BaseModel):
    season: int
    season_type: str
    team_name: str | None = None
    position: str | None = None
    games_played: int | None = None
    games_started: int | None = None
    summary: list[HistoricalStatValue]
    categories: list[HistoricalStatsCategory]
    freshness: HistoricalStatsFreshness
    scoring_context: HistoricalStatsScoringContext
    unknown_labels: dict[str, Any] | None = None


class PlayerHistoricalStatsResponse(BaseModel):
    player_id: int
    provider: str = "espn"
    status: HistoricalStatsStatus
    message: str | None = None
    selected_season: int | None = None
    available_seasons: list[int] = []
    seasons: list[PlayerHistoricalSeasonRead] = []
