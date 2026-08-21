from datetime import datetime

from pydantic import BaseModel


class PostseasonTeamRead(BaseModel):
    team_id: int
    team_name: str
    manager_name: str | None = None
    manager_avatar_url: str | None = None


class PostseasonSeedRead(PostseasonTeamRead):
    seed: int
    regular_season_rank: int
    wins: int
    losses: int
    ties: int
    points_for: float
    tiebreaker_explanation: str | None = None


class PostseasonMatchupRead(BaseModel):
    id: int
    round_number: int
    week: int
    matchup_type: str
    bracket_path: str | None = None
    status: str
    fantasy_matchup_id: int | None = None
    team_a: PostseasonTeamRead | None = None
    team_b: PostseasonTeamRead | None = None
    team_a_seed: int | None = None
    team_b_seed: int | None = None
    team_a_score: float | None = None
    team_b_score: float | None = None
    winner_team_id: int | None = None
    loser_team_id: int | None = None
    tiebreaker_used: str | None = None
    next_winner_matchup_id: int | None = None
    next_loser_matchup_id: int | None = None


class PostseasonRoundRead(BaseModel):
    round_number: int
    week: int
    status: str
    matchups: list[PostseasonMatchupRead]


class PostseasonFinalStandingRead(PostseasonTeamRead):
    final_place: int
    regular_season_rank: int
    playoff_seed: int | None = None
    postseason_result: str


class PostseasonRead(BaseModel):
    league_id: int
    season: int
    status: str
    is_preview: bool
    playoff_teams: int
    regular_season_end_week: int
    playoff_start_week: int
    current_fantasy_week: int | None = None
    format_version: str
    tiebreaker_policy: str
    format_summary: str
    seeds_locked_at: datetime | None = None
    champion: PostseasonTeamRead | None = None
    review_reason: str | None = None
    seeds: list[PostseasonSeedRead] = []
    playoff_cut_line: int | None = None


class PostseasonBracketRead(PostseasonRead):
    rounds: list[PostseasonRoundRead] = []
    final_standings: list[PostseasonFinalStandingRead] = []
