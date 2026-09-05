from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from collegefootballfantasy_api.app.schemas.waiver import WaiverClaimRead, WaiverDropCandidateRead
from collegefootballfantasy_api.app.schemas.rivalry import RivalryMatchupRead


MIN_LEAGUE_TEAM_COUNT = 2
MAX_LEAGUE_TEAM_COUNT = 14


def _validate_iana_timezone(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("waiver_timezone must be a valid IANA timezone")
    try:
        ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("waiver_timezone must be a valid IANA timezone") from exc
    return normalized


class LeagueBasics(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    season_year: int
    max_teams: int
    is_private: bool = True
    description: str | None = Field(default=None, max_length=500)
    icon_url: str | None = Field(default=None, max_length=2048)

    @field_validator("is_private")
    @classmethod
    def normalize_invite_only_leagues(cls, _value: bool) -> bool:
        """Keep legacy clients compatible while enforcing invite-only leagues."""
        return True

    @field_validator("max_teams")
    @classmethod
    def validate_even_manager_count(cls, value: int) -> int:
        if value < MIN_LEAGUE_TEAM_COUNT or value > MAX_LEAGUE_TEAM_COUNT or value % 2 != 0:
            raise ValueError(
                f"max_teams must be an even number between {MIN_LEAGUE_TEAM_COUNT} and {MAX_LEAGUE_TEAM_COUNT}"
            )
        return value


class LeagueSettingsInput(BaseModel):
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    waiver_period_hours: int = 24
    waiver_processing_weekday: int = Field(
        default=6,
        validation_alias=AliasChoices("waiver_processing_weekday", "waiver_process_day"),
    )
    waiver_processing_hour: int = Field(
        default=8,
        validation_alias=AliasChoices("waiver_processing_hour", "waiver_process_hour"),
    )
    waiver_timezone: str = "America/New_York"
    faab_starting_budget: int = Field(
        default=100,
        validation_alias=AliasChoices("faab_starting_budget", "faab_budget"),
    )
    allow_zero_faab_bids: bool = Field(
        default=True,
        validation_alias=AliasChoices("allow_zero_faab_bids", "allow_zero_dollar_bids"),
    )
    waiver_tiebreaker: str = "priority"
    initial_waiver_priority_method: str = "reverse_draft"
    reveal_all_waiver_bids: bool = False
    post_drop_waiver_hours: int = 24
    trade_review_type: str = "league_vote"
    trade_deadline_week: int | None = None
    trade_deadline_at: datetime | None = None
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool

    @field_validator("playoff_teams")
    @classmethod
    def validate_playoff_teams(cls, value: int) -> int:
        if value not in {2, 4, 6, 8}:
            raise ValueError("playoff_teams must be one of 2, 4, 6, or 8")
        return value

    @field_validator("waiver_period_hours")
    @classmethod
    def validate_waiver_period_hours(cls, value: int) -> int:
        if value < 1 or value > 168:
            raise ValueError("waiver_period_hours must be between 1 and 168")
        return value

    @field_validator("waiver_type")
    @classmethod
    def validate_waiver_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"faab", "priority"}:
            raise ValueError("waiver_type must be faab or priority")
        return normalized

    @field_validator("waiver_processing_weekday")
    @classmethod
    def validate_waiver_processing_weekday(cls, value: int) -> int:
        if value < 0 or value > 6:
            raise ValueError("waiver_processing_weekday must be between 0 and 6")
        return value

    @field_validator("waiver_processing_hour")
    @classmethod
    def validate_waiver_processing_hour(cls, value: int) -> int:
        if value < 0 or value > 23:
            raise ValueError("waiver_processing_hour must be between 0 and 23")
        return value

    @field_validator("waiver_timezone")
    @classmethod
    def validate_waiver_timezone(cls, value: str) -> str:
        return _validate_iana_timezone(value)

    @field_validator("faab_starting_budget", "post_drop_waiver_hours")
    @classmethod
    def validate_nonnegative_waiver_values(cls, value: int) -> int:
        if value < 0:
            raise ValueError("waiver configuration values cannot be negative")
        return value

    @field_validator("trade_review_type")
    @classmethod
    def validate_trade_review_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"none", "commissioner", "league_vote"}:
            raise ValueError("trade_review_type must be league_vote")
        # Keep pre-release clients compatible while enforcing the sole
        # supported rule for each new league.
        return "league_vote"

    @field_validator("waiver_tiebreaker")
    @classmethod
    def validate_waiver_tiebreaker(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"priority", "earliest_claim"}:
            raise ValueError("waiver_tiebreaker must be priority or earliest_claim")
        return normalized


class DraftScheduleInput(BaseModel):
    draft_datetime_utc: datetime
    timezone: str
    draft_type: str
    draft_order_mode: str = "random"
    pick_timer_seconds: int

    @field_validator("draft_order_mode")
    @classmethod
    def validate_draft_order_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"random", "custom"}:
            raise ValueError("draft_order_mode must be random or custom")
        return normalized


class LeagueCreateRequest(BaseModel):
    basics: LeagueBasics
    settings: LeagueSettingsInput
    draft: DraftScheduleInput
    beta_scoring_acknowledged: bool = False


class LeagueMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    role: str
    joined_at: datetime
    manager_name: str | None = None
    manager_avatar_url: str | None = None


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    league_id: int
    draft_datetime_utc: datetime
    timezone: str
    draft_type: str
    draft_order_mode: str
    pick_timer_seconds: int
    status: str


class DraftOrderEntryRead(BaseModel):
    team_id: int
    team_name: str
    owner_user_id: int | None = None
    owner_name: str | None = None
    owner_avatar_url: str | None = None
    draft_position: int | None = None


class DraftOrderRead(BaseModel):
    draft_order_mode: str
    max_teams: int
    is_complete: bool
    entries: list[DraftOrderEntryRead]


class DraftOrderEntryInput(BaseModel):
    team_id: int
    draft_position: int = Field(ge=1)


class DraftOrderUpdate(BaseModel):
    draft_order_mode: str
    entries: list[DraftOrderEntryInput] = Field(default_factory=list)

    @field_validator("draft_order_mode")
    @classmethod
    def validate_draft_order_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"random", "custom"}:
            raise ValueError("draft_order_mode must be random or custom")
        return normalized


class LeagueSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    league_id: int
    scoring_json: dict
    scoring_snapshot_json: dict | None = None
    scoring_locked_at: datetime | None = None
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    waiver_period_hours: int
    waiver_processing_weekday: int
    waiver_processing_hour: int
    waiver_timezone: str
    waiver_process_day: int
    waiver_process_hour: int
    next_waiver_run_at: datetime | None
    faab_starting_budget: int
    allow_zero_faab_bids: bool
    faab_budget: int
    allow_zero_dollar_bids: bool
    waiver_tiebreaker: str
    initial_waiver_priority_method: str
    reveal_all_waiver_bids: bool
    post_drop_waiver_hours: int
    waivers_enabled: bool
    free_agent_mode: str
    trade_review_type: str = "league_vote"
    trade_deadline_week: int | None
    trade_deadline_at: datetime | None
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool


class LeagueSettingsUpdate(BaseModel):
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    waiver_period_hours: int | None = None
    waiver_processing_weekday: int | None = Field(
        default=None,
        validation_alias=AliasChoices("waiver_processing_weekday", "waiver_process_day"),
    )
    waiver_processing_hour: int | None = Field(
        default=None,
        validation_alias=AliasChoices("waiver_processing_hour", "waiver_process_hour"),
    )
    waiver_timezone: str | None = None
    faab_starting_budget: int | None = Field(
        default=None,
        validation_alias=AliasChoices("faab_starting_budget", "faab_budget"),
    )
    allow_zero_faab_bids: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("allow_zero_faab_bids", "allow_zero_dollar_bids"),
    )
    waiver_tiebreaker: str | None = None
    initial_waiver_priority_method: str | None = None
    reveal_all_waiver_bids: bool | None = None
    post_drop_waiver_hours: int | None = None
    trade_review_type: str
    trade_deadline_week: int | None = None
    trade_deadline_at: datetime | None = None
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool

    @field_validator("playoff_teams")
    @classmethod
    def validate_playoff_teams(cls, value: int) -> int:
        if value not in {2, 4, 6, 8}:
            raise ValueError("playoff_teams must be one of 2, 4, 6, or 8")
        return value

    @field_validator("waiver_period_hours")
    @classmethod
    def validate_waiver_period_hours(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 1 or value > 168:
            raise ValueError("waiver_period_hours must be between 1 and 168")
        return value

    @field_validator("waiver_processing_weekday")
    @classmethod
    def validate_updated_waiver_processing_weekday(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 0 or value > 6:
            raise ValueError("waiver_processing_weekday must be between 0 and 6")
        return value

    @field_validator("waiver_processing_hour")
    @classmethod
    def validate_updated_waiver_processing_hour(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 0 or value > 23:
            raise ValueError("waiver_processing_hour must be between 0 and 23")
        return value

    @field_validator("waiver_timezone")
    @classmethod
    def validate_updated_waiver_timezone(cls, value: str | None) -> str | None:
        return _validate_iana_timezone(value) if value is not None else None

    @field_validator("faab_starting_budget", "post_drop_waiver_hours")
    @classmethod
    def validate_updated_nonnegative_waiver_values(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("waiver configuration values cannot be negative")
        return value

    @field_validator("waiver_type")
    @classmethod
    def validate_updated_waiver_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"faab", "priority"}:
            raise ValueError("waiver_type must be faab or priority")
        return normalized

    @field_validator("trade_review_type")
    @classmethod
    def validate_updated_trade_review_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"none", "commissioner", "league_vote"}:
            raise ValueError("trade_review_type must be league_vote")
        return "league_vote"

    @field_validator("waiver_tiebreaker")
    @classmethod
    def validate_optional_waiver_tiebreaker(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"priority", "earliest_claim"}:
            raise ValueError("waiver_tiebreaker must be priority or earliest_claim")
        return normalized


class DraftUpdate(BaseModel):
    draft_datetime_utc: datetime
    timezone: str
    draft_type: str
    pick_timer_seconds: int
    status: str = "scheduled"

    @field_validator("draft_datetime_utc")
    @classmethod
    def validate_timezone_aware_draft_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("draft_datetime_utc must include a timezone offset")
        return value.astimezone(timezone.utc)

    @field_validator("timezone")
    @classmethod
    def validate_draft_timezone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("timezone must be a valid IANA timezone")
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return normalized


class LeagueListCurrentUserSummaryRead(BaseModel):
    """The signed-in member's compact, source-of-truth league card summary."""

    team_name: str | None = None
    wins: int | None = None
    losses: int | None = None
    ties: int | None = None
    opponent_team_name: str | None = None
    matchup_week: int | None = None
    projected_points_for: float | None = None
    projected_points_against: float | None = None
    win_probability_for: float | None = None
    win_probability_against: float | None = None
    is_rivalry_matchup: bool = False


class LeagueDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    commissioner_user_id: int | None
    commissioner_name: str | None = None
    commissioner_avatar_url: str | None = None
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
    draft_order: DraftOrderRead | None = None
    members: list[LeagueMemberRead]
    current_user_summary: LeagueListCurrentUserSummaryRead | None = None


class LeagueWorkspaceTeamRead(BaseModel):
    id: int
    league_id: int
    name: str
    owner_user_id: int | None = None


class LeagueWorkspaceRosterEntryRead(BaseModel):
    id: int
    team_id: int
    player_id: int
    slot: str
    status: str
    player_name: str | None = None
    player_school: str | None = None
    player_position: str | None = None


class LeagueWorkspaceMatchupSummaryRead(BaseModel):
    week: int | None = None
    team_id: int | None = None
    opponent_team_id: int | None = None
    opponent_team_name: str | None = None
    status: str | None = None
    projected_points_for: float | None = None
    projected_points_against: float | None = None
    win_probability_for: float | None = None
    win_probability_against: float | None = None
    is_rivalry_matchup: bool = False


class LeagueWorkspaceStandingSummaryRead(BaseModel):
    team_id: int
    team_name: str
    wins: int | None = None
    losses: int | None = None
    ties: int | None = None
    points_for: float | None = None
    rank: int | None = None


class LeagueWorkspaceRead(BaseModel):
    league: LeagueDetailRead
    membership: LeagueMemberRead | None = None
    owned_team: LeagueWorkspaceTeamRead | None = None
    roster: list[LeagueWorkspaceRosterEntryRead]
    matchup_summary: LeagueWorkspaceMatchupSummaryRead | None = None
    standings_summary: list[LeagueWorkspaceStandingSummaryRead]
    allowed_actions: list[str]


class LeagueScoreboardRow(BaseModel):
    matchup_id: int
    week: int
    status: str
    home_team_id: int
    home_team_name: str
    home_owner_avatar_url: str | None = None
    home_score: float
    away_team_id: int
    away_team_name: str
    away_owner_avatar_url: str | None = None
    away_score: float


class LeagueScoreboardList(BaseModel):
    data: list[LeagueScoreboardRow]
    total: int


class LeaguePowerRankingRow(BaseModel):
    team_id: int
    team_name: str
    rank: int
    wins: int
    losses: int
    ties: int
    points_for: float


class LeaguePowerRankingList(BaseModel):
    data: list[LeaguePowerRankingRow]
    total: int


class LeagueNewsItem(BaseModel):
    id: int
    team_id: int
    team_name: str | None = None
    transaction_type: str
    headline: str
    detail: str | None = None
    created_at: datetime


class LeagueNewsList(BaseModel):
    data: list[LeagueNewsItem]
    total: int
    limit: int


class LeagueCreateResponse(BaseModel):
    league: LeagueDetailRead
    invite_code: str
    invite_link: str


class LeaguePreview(BaseModel):
    id: int
    name: str
    commissioner_name: str | None
    commissioner_avatar_url: str | None = None
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


class RosterTabTeamRead(BaseModel):
    id: int
    name: str
    owner_user_id: int | None = None
    owner_name: str | None = None
    owner_avatar_url: str | None = None
    record: str | None = None


class PlayerPopularityRead(BaseModel):
    rostered_percent: float | None = None
    start_percent: float | None = None


class PlayerPopularitySnapshotRead(BaseModel):
    as_of: datetime | None = None
    coverage_started_at: datetime | None = None
    status: str = "unavailable"


class RosterTabEntryRead(BaseModel):
    id: int | None = None
    league_id: int | None = None
    team_id: int
    fantasy_team_id: int | None = None
    fantasy_team_name: str | None = None
    player_id: int | None = None
    slot: str
    slot_id: str
    slot_index: int
    display_label: str
    roster_slot: str | None = None
    # Real-world report status; `status` remains the fantasy roster state.
    injury_status: str | None = None
    status: str
    is_starter: bool
    is_ir: bool
    player_name: str | None = None
    player_school: str | None = None
    player_position: str | None = None
    school: str | None = None
    position: str | None = None
    projected_points: float | None = None
    floor: float = 0.0
    ceiling: float = 0.0
    boom_prob: float = 0.0
    bust_prob: float = 0.0
    opponent: str | None = None
    game_location: str | None = None
    weekly_projected_fantasy_points: float | None = None
    projection_status: str = "UNAVAILABLE"
    live_points: float | None = None
    live_scoring_status: str = "unavailable"
    live_scoring_updated_at: datetime | None = None
    current_fantasy_points: float | None = None
    pregame_projected_points: float | None = None
    live_projected_final_points: float | None = None
    live_projection_status: str | None = None
    live_projection_model_version: str | None = None
    projection_updated_at: datetime | None = None
    provider_snapshot_at: datetime | None = None
    game_period: int | None = None
    game_clock: str | None = None
    game_score: str | None = None
    game_down_distance: str | None = None
    game_is_halftime: bool = False
    game_progress: float | None = None
    live_projection_fallback_reason: str | None = None
    live_game_state: str = "unavailable"
    team_has_possession: bool = False
    team_in_red_zone: bool = False
    game_start_at: datetime | None = None
    # A compact position-specific cumulative stat line for this player's
    # current game. It is refreshed from live snapshots and retained as the
    # verified final line once the game ends.
    game_stat_line: str | None = None
    # A compact, verified final box-score summary for this player's current
    # roster-row game. This is deliberately display-ready rather than the
    # provider's full stat payload.
    final_game_stat_line: str | None = None
    popularity: PlayerPopularityRead | None = None
    is_locked: bool = False
    acquisition_type: str = "ROSTER"
    draft_pick_id: int | None = None


class LeagueRosterTeamRead(BaseModel):
    team: RosterTabTeamRead
    roster: list[RosterTabEntryRead]


class LeagueRosterTabRead(BaseModel):
    league_id: int
    season: int
    week: int
    owned_team: RosterTabTeamRead | None = None
    roster: list[RosterTabEntryRead]
    roster_slot_limits: dict[str, int]
    ir_slots: int
    message: str | None = None
    fantasy_team_id: int | None = None
    fantasy_team_name: str | None = None
    data: list[RosterTabEntryRead] = []
    slots: list[RosterTabEntryRead] = []
    team_rosters: list[LeagueRosterTeamRead] = []
    popularity_snapshot: PlayerPopularitySnapshotRead | None = None


class MatchupTeamRead(BaseModel):
    id: int
    name: str
    record: str | None = None
    projected_points: float | None = None
    win_probability: float | None = None
    fantasy_team_id: int
    fantasy_team_name: str
    manager_name: str | None = None
    owner_avatar_url: str | None = None
    projected_total: float | None = None
    current_points: float | None = None
    pregame_projected_total: float | None = None
    live_projected_total: float | None = None
    roster: list[RosterTabEntryRead]


class LiveScoringFreshnessRead(BaseModel):
    """Provider freshness metadata for a stored matchup score.

    The matchup endpoint never calls an external provider.  This shape makes
    the age and condition of the worker's last persisted provider data visible
    to the client instead of implying that every displayed live score is fresh.
    """

    provider: str | None = None
    state: str = "unavailable"
    provider_as_of: datetime | None = None
    last_successful_update_at: datetime | None = None
    data_age_seconds: int | None = None
    relevant_game_count: int = 0


class PostseasonMatchupContextRead(BaseModel):
    bracket_id: int
    matchup_type: str
    bracket_path: str | None = None
    status: str


class LeagueMatchupTabRead(BaseModel):
    league_id: int
    season: int
    week: int
    week_started: bool = False
    matchup_id: int | None = None
    status: str | None = None
    my_team: MatchupTeamRead | None = None
    opponent_team: MatchupTeamRead | None = None
    my_roster: list[RosterTabEntryRead]
    opponent_roster: list[RosterTabEntryRead]
    projection_source: str = "weekly_projections"
    live_scoring_freshness: LiveScoringFreshnessRead | None = None
    projection_updated_at: datetime | None = None
    provider_snapshot_at: datetime | None = None
    next_refresh_at: datetime | None = None
    message: str | None = None
    user_team: MatchupTeamRead | None = None
    rivalry: RivalryMatchupRead | None = None
    postseason: PostseasonMatchupContextRead | None = None


class LeagueWaiverPlayerRead(BaseModel):
    id: int
    name: str
    school: str | None = None
    opponent: str | None = None
    position: str | None = None
    weekly_projected_fantasy_points: float | None = None
    # This is populated only from a verified final box score.  Keeping it
    # separate from the forecast prevents a completed-game total from being
    # mislabeled as a projection in the waiver wire.
    final_fantasy_points: float | None = None
    projection_status: str = "UNAVAILABLE"
    # The All Players research view includes league-rostered players.  They
    # remain visible for trade research and watchlists but can never be added
    # through the waiver workflow.
    rostered_by_team_name: str | None = None
    availability_state: str = "waivers"
    available_at: datetime | None = None
    popularity: PlayerPopularityRead | None = None
    hot_pickup_count: int | None = None


class LeagueWaiverPeriodRead(BaseModel):
    id: int
    season: int
    week: int
    window_key: str
    opens_at: datetime
    closes_at: datetime
    processes_at: datetime
    status: str


class LeagueWaiversRead(BaseModel):
    league_id: int
    fantasy_team_id: int | None = None
    waiver_priority: int | None = None
    faab_remaining: int | None = None
    available_players: list[LeagueWaiverPlayerRead]
    claims: list[WaiverClaimRead] = []
    current_period: LeagueWaiverPeriodRead | None = None
    results_period: LeagueWaiverPeriodRead | None = None
    results: list[WaiverClaimRead] = []
    roster: list[WaiverDropCandidateRead] = []
    waiver_rules: dict = {}
    total_available: int
    message: str | None = None
    popularity_snapshot: PlayerPopularitySnapshotRead | None = None


class LeagueScoreRecalculateResponse(BaseModel):
    league_id: int
    season: int
    week: int
    players_scored: int
    teams_scored: int
    matchups_updated: int
    standings_updated: int


class LeagueScheduleRowRead(BaseModel):
    matchup_id: int
    week: int
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_projected_total: float = 0.0
    away_projected_total: float = 0.0
    home_win_probability: float = 50.0
    away_win_probability: float = 50.0


class LeagueInviteSettingsRead(BaseModel):
    code: str
    link: str
    draft_status: str | None = None
    visible_until_draft_complete: bool = True


class LeagueTradeHistoryPartyRead(BaseModel):
    team_id: int
    team_name: str
    manager_name: str | None = None
    manager_avatar_url: str | None = None


class LeagueTradeHistoryAssetRead(BaseModel):
    player_id: int | None = None
    name: str
    position: str | None = None
    school: str | None = None


class LeagueTradeHistoryRead(BaseModel):
    id: int
    status: str
    proposing_party: LeagueTradeHistoryPartyRead
    receiving_party: LeagueTradeHistoryPartyRead
    proposing_team_sends: list[LeagueTradeHistoryAssetRead]
    receiving_team_sends: list[LeagueTradeHistoryAssetRead]
    created_at: datetime
    accepted_at: datetime | None = None
    processed_at: datetime | None = None


class LeagueSettingsViewRead(BaseModel):
    league_id: int
    league_name: str
    league_info: dict
    postseason_calendar: dict[str, int | str] | None = None
    invite: LeagueInviteSettingsRead | None = None
    members: list[LeagueMemberRead]
    teams: list[LeagueWorkspaceTeamRead]
    scoring_settings: dict
    roster_settings: dict[str, int]
    waiver_rules: dict
    standings: list[dict]
    schedule: list[LeagueScheduleRowRead]
    rosters: list[RosterTabEntryRead]
    trade_history: list[LeagueTradeHistoryRead]
    draft_results: list[dict]
    commissioner_controls: list[str]
