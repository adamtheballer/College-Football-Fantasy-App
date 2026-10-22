from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer
from collegefootballfantasy_api.app.core.config import settings


class RankedPlayer(BaseModel):
    id: int
    name: str
    school: str
    position: str
    image_url: str | None = None
    fantasy_points: float | None
    position_rank: int | None
    games: int
    missing_games: int
    status: Literal["final", "pending", "bye", "ineligible"]
    stats: dict[str, float]
    updated_at: datetime | None
    on_my_roster: bool = False

    @field_serializer("image_url")
    def public_image(self, value: str | None) -> str | None:
        return value if settings.player_headshots_enabled else None


class RankingContext(BaseModel):
    season: int
    period: Literal["week", "season"]
    week: int | None
    through_week: int
    available_weeks: list[int]
    league_id: int | None
    scoring_label: str
    verified_players: int
    pending_players: int
    updated_at: datetime | None


class PlayerRankings(RankingContext):
    data: list[RankedPlayer]
    total: int
    limit: int
    offset: int


class PositionLeader(BaseModel):
    position: str
    player: RankedPlayer | None


class PlayerLeaders(RankingContext):
    data: list[PositionLeader]
