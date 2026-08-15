from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PlayoffSeedRecordRead(BaseModel):
    wins: int
    losses: int
    ties: int
    games_played: int
    winning_percentage: float | None
    points_for: float
    points_against: float


class PlayoffSeedRead(BaseModel):
    seed: int
    team_id: int
    team_name: str
    record: PlayoffSeedRecordRead
    qualified: bool
    resolved_by: str
    tiebreak_group_team_ids: list[int] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class PlayoffSeedingRead(BaseModel):
    league_id: int
    season: int
    state: str
    playoff_team_count: int
    seeding_locked_at: datetime | None
    tiebreak_order: list[str]
    entries: list[PlayoffSeedRead]


class PlayoffBracketTeamRead(BaseModel):
    team_id: int | None
    team_name: str | None
    seed: int | None


class PlayoffBracketRoundRead(BaseModel):
    round_number: int
    round_type: str
    week: int
    slot_number: int
    status: str
    team_a: PlayoffBracketTeamRead
    team_b: PlayoffBracketTeamRead
    advancing_team_id: int | None
    tiebreaker_used: str | None
    fantasy_matchup_id: int | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlayoffBracketEntryRead(BaseModel):
    team_id: int
    team_name: str
    seed: int
    regular_season_rank: int
    status: str
    explanation: dict[str, Any] | None


class PlayoffBracketRead(BaseModel):
    league_id: int
    season: int
    status: str
    generated_at: datetime | None
    finalized_at: datetime | None
    seeding_locked_at: datetime | None
    entries: list[PlayoffBracketEntryRead]
    rounds: list[PlayoffBracketRoundRead]


class PlayoffFinalizeRead(BaseModel):
    finalized_matchups: int
    bracket: PlayoffBracketRead | None
