from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from collegefootballfantasy_api.app.schemas.waiver import WaiverClaimRead, WaiverDropCandidateRead


class LeagueBasics(BaseModel):
    name: str
    season_year: int
    max_teams: int
    is_private: bool = True
    description: str | None = None
    icon_url: str | None = None

    @field_validator("max_teams")
    @classmethod
    def validate_even_manager_count(cls, value: int) -> int:
        if value < 2 or value % 2 != 0:
            raise ValueError("max_teams must be an even number of at least 2")
        return value


class LeagueSettingsInput(BaseModel):
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    waiver_period_hours: int = 24
    waiver_process_day: int = 2
    waiver_process_hour: int = 3
    faab_budget: int = 100
    allow_zero_dollar_bids: bool = True
    waiver_tiebreaker: str = "priority"
    initial_waiver_priority_method: str = "reverse_draft"
    post_drop_waiver_hours: int = 24
    trade_review_type: str
    trade_deadline_week: int | None = None
    trade_deadline_at: datetime | None = None
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool

    @field_validator("waiver_period_hours")
    @classmethod
    def validate_waiver_period_hours(cls, value: int) -> int:
        if value < 1 or value > 168:
            raise ValueError("waiver_period_hours must be between 1 and 168")
        return value

    @field_validator("waiver_process_day")
    @classmethod
    def validate_waiver_process_day(cls, value: int) -> int:
        if value < 0 or value > 6:
            raise ValueError("waiver_process_day must be between 0 and 6")
        return value

    @field_validator("waiver_process_hour")
    @classmethod
    def validate_waiver_process_hour(cls, value: int) -> int:
        if value < 0 or value > 23:
            raise ValueError("waiver_process_hour must be between 0 and 23")
        return value

    @field_validator("trade_review_type")
    @classmethod
    def validate_trade_review_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"none", "commissioner"}:
            raise ValueError("trade_review_type must be none or commissioner")
        return normalized

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
    waiver_period_hours: int
    waiver_process_day: int
    waiver_process_hour: int
    next_waiver_run_at: datetime | None
    faab_budget: int
    allow_zero_dollar_bids: bool
    waiver_tiebreaker: str
    initial_waiver_priority_method: str
    post_drop_waiver_hours: int
    trade_review_type: str
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
    waiver_process_day: int | None = None
    waiver_process_hour: int | None = None
    faab_budget: int | None = None
    allow_zero_dollar_bids: bool | None = None
    waiver_tiebreaker: str | None = None
    initial_waiver_priority_method: str | None = None
    post_drop_waiver_hours: int | None = None
    trade_review_type: str
    trade_deadline_week: int | None = None
    trade_deadline_at: datetime | None = None
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool

    @field_validator("waiver_period_hours")
    @classmethod
    def validate_waiver_period_hours(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 1 or value > 168:
            raise ValueError("waiver_period_hours must be between 1 and 168")
        return value

    @field_validator("trade_review_type")
    @classmethod
    def validate_updated_trade_review_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"none", "commissioner"}:
            raise ValueError("trade_review_type must be none or commissioner")
        return normalized

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
    home_score: float
    away_team_id: int
    away_team_name: str
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
    record: str | None = None


class RosterTabEntryRead(BaseModel):
    id: int
    league_id: int | None = None
    team_id: int
    fantasy_team_id: int | None = None
    fantasy_team_name: str | None = None
    player_id: int
    slot: str
    roster_slot: str | None = None
    status: str
    is_starter: bool
    is_ir: bool
    player_name: str | None = None
    player_school: str | None = None
    player_position: str | None = None
    school: str | None = None
    position: str | None = None
    projected_points: float = 0.0
    floor: float = 0.0
    ceiling: float = 0.0
    boom_prob: float = 0.0
    bust_prob: float = 0.0
    opponent: str | None = None
    weekly_projected_fantasy_points: float = 0.0
    acquisition_type: str = "ROSTER"
    draft_pick_id: int | None = None


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


class MatchupTeamRead(BaseModel):
    id: int
    name: str
    record: str | None = None
    projected_points: float = 0.0
    win_probability: float = 50.0
    fantasy_team_id: int
    fantasy_team_name: str
    projected_total: float = 0.0
    roster: list[RosterTabEntryRead]


class LeagueMatchupTabRead(BaseModel):
    league_id: int
    season: int
    week: int
    matchup_id: int | None = None
    status: str | None = None
    my_team: MatchupTeamRead | None = None
    opponent_team: MatchupTeamRead | None = None
    my_roster: list[RosterTabEntryRead]
    opponent_roster: list[RosterTabEntryRead]
    projection_source: str = "weekly_projections"
    message: str | None = None
    user_team: MatchupTeamRead | None = None


class LeagueWaiverPlayerRead(BaseModel):
    id: int
    name: str
    school: str | None = None
    position: str | None = None
    weekly_projected_fantasy_points: float = 0.0


class LeagueWaiversRead(BaseModel):
    league_id: int
    fantasy_team_id: int | None = None
    available_players: list[LeagueWaiverPlayerRead]
    claims: list[WaiverClaimRead] = []
    roster: list[WaiverDropCandidateRead] = []
    waiver_rules: dict = {}
    total_available: int
    message: str | None = None


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


class LeagueSettingsViewRead(BaseModel):
    league_id: int
    league_name: str
    league_info: dict
    invite: LeagueInviteSettingsRead | None = None
    members: list[LeagueMemberRead]
    scoring_settings: dict
    roster_settings: dict[str, int]
    waiver_rules: dict
    standings: list[dict]
    schedule: list[LeagueScheduleRowRead]
    rosters: list[RosterTabEntryRead]
    draft_results: list[dict]
    commissioner_controls: list[str]
