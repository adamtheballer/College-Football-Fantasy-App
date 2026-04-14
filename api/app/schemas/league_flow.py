from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeagueBasics(BaseModel):
    name: str
    season_year: int
    max_teams: int
    is_private: bool = True
    description: str | None = None
    icon_url: str | None = None


class LeagueSettingsInput(BaseModel):
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    trade_review_type: str
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool


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
    trade_review_type: str
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool


class LeagueSettingsUpdate(BaseModel):
    scoring_json: dict
    roster_slots_json: dict
    playoff_teams: int
    waiver_type: str
    trade_review_type: str
    superflex_enabled: bool
    kicker_enabled: bool
    defense_enabled: bool


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
