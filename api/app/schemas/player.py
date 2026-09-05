from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_serializer

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.schemas.historical_stats import PlayerHistoricalStatsResponse
from collegefootballfantasy_api.app.services.power4 import canonical_school_name


class PlayerBase(BaseModel):
    external_id: str | None = None
    name: str
    position: str
    school: str
    image_url: str | None = None
    player_class: str | None = None
    sheet_adp: float | None = None
    sheet_projected_season_points: float | None = None
    sheet_projection_stats: dict | None = None
    sheet_source_sheet_id: str | None = None
    sheet_synced_at: datetime | None = None
    cfb27_rank: int | None = None
    cfb27_overall: int | None = None
    cfb27_position_rank: int | None = None
    cfb27_synced_at: datetime | None = None
    raw_cfb27_rating: int | None = None
    current_value_rating: float | None = None
    value_policy_version: str | None = None
    value_calculation_week: int | None = None
    value_calculated_at: datetime | None = None
    value_source_batch_id: str | None = None


class PlayerCreate(PlayerBase):
    pass


class PlayerRead(PlayerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Read-only master-board outlook.  These values are calculated from the
    # authoritative weekly projection series and must never enter PlayerCreate
    # or the persisted players table.
    rest_of_season_projected_points: float | None = None
    rest_of_season_rank: int | None = None
    rest_of_season_as_of_week: int | None = None
    rest_of_season_updated_at: datetime | None = None
    board_rank: int | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("image_url")
    def serialize_player_image_url(self, value: str | None) -> str | None:
        """Preserve the nullable contract while withholding unlicensed portraits."""
        return value if settings.player_headshots_enabled else None

    @field_serializer("school")
    def serialize_school(self, value: str) -> str:
        """Keep canonical school capitalization consistent in every player response."""
        return canonical_school_name(value) or value


class PlayerList(BaseModel):
    data: list[PlayerRead]
    total: int
    limit: int
    offset: int


class PlayerCardAboutRead(BaseModel):
    espn_player_id: str | None = None
    height: str | None = None
    weight: str | None = None
    player_class: str | None = None
    birthplace: str | None = None
    status: str | None = None
    jersey: str | None = None
    position: str | None = None
    team: str | None = None
    headshot_url: str | None = None
    source: str = "local"
    message: str | None = None


class PlayerCardInjuryRead(BaseModel):
    id: int
    season: int
    week: int
    status: str
    injury: str | None = None
    return_timeline: str | None = None
    practice_level: str | None = None
    is_game_time_decision: bool = False
    is_returning: bool = False
    notes: str | None = None
    updated_at: datetime


class PlayerCardStatRowRead(BaseModel):
    season: int
    week: int
    source: str
    stats: dict
    updated_at: datetime


class PlayerCardGameDisplayRead(BaseModel):
    """Real-game context: live/awaiting_live/completed/upcoming/unavailable.

    Live statistics are game-keyed and independent of league-week scoring.
    Kickoff timestamps include a timezone; clients render them in local time.
    """

    state: str
    season: int | None = None
    week: int | None = None
    game_id: int | None = None
    opponent_name: str | None = None
    kickoff_at: datetime | None = None
    transition_at: datetime | None = None
    stats: dict | None = None
    source: str | None = None
    updated_at: datetime | None = None


class PlayerCardSeasonRankRead(BaseModel):
    """Cumulative, same-position fantasy rank after finalized weeks only."""

    position: str
    rank: int
    fantasy_points: float
    through_week: int


class PlayerSeasonOutlookRead(BaseModel):
    """Public, persisted copy only; the evidence record remains server-side."""

    model_config = ConfigDict(from_attributes=True)

    season_year: int
    outlook_type: str
    outlook_text: str
    generator_version: str
    generated_at: datetime
    review_status: str


class PlayerCardNewsRead(BaseModel):
    id: int
    event_type: str
    status: str | None = None
    detail: str | None = None
    source: str
    source_url: str | None = None
    published_at: datetime | None = None
    return_timeline: str | None = None


class PlayerCardRead(BaseModel):
    player: PlayerRead
    about: PlayerCardAboutRead
    current_injury_status: str | None = None
    injuries: list[PlayerCardInjuryRead]
    recent_news: list[PlayerCardNewsRead] = []
    season_stats: list[PlayerCardStatRowRead]
    season_positional_rank: PlayerCardSeasonRankRead | None = None
    current_game: PlayerCardGameDisplayRead | None = None
    season_outlook: PlayerSeasonOutlookRead | None = None
    historical_stats: PlayerHistoricalStatsResponse | None = None
