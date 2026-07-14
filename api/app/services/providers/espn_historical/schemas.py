from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


PARSER_VERSION = "espn-historical-v1"
SCHEMA_VERSION = "espn-athlete-stats-v1"
SOURCE_REVISION = "danabrey/espn-college-football-stats@def7d08e8e91018106747675acad927a9c5955b3"


@dataclass(frozen=True)
class ParsedNumber:
    value: float | None
    raw: Any
    warning: str | None = None


@dataclass
class ProviderPlayerSeason:
    season: int
    season_type: str = "regular"
    team_provider_id: str | None = None
    team_name: str | None = None
    position: str | None = None
    games_played: int | None = None
    games_started: int | None = None
    categories: dict[str, dict[str, float | None]] = field(default_factory=dict)
    raw_labels: dict[str, dict[str, Any]] = field(default_factory=dict)
    unknown_labels: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_url: str | None = None
    provider_updated_at: datetime | None = None
    is_complete: bool = True
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProviderPlayerHistory:
    provider: str
    provider_player_id: str
    player_name: str | None
    fetched_at: datetime
    source_revision: str
    seasons: list[ProviderPlayerSeason]
    raw_payload: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    available: bool
    message: str | None = None
