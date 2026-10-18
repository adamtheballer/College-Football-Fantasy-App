from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .challenge_primitives import StrictModel, Selection, Participant, GameRead
from .challenge_experience import ExperienceRead

ChallengeKind = Literal["slate12", "upset", "fantasy5", "lock", "duels", "fanwars", "millionaire", "creator", "survivor"]


class Underdog(StrictModel):
    game_id: int = Field(gt=0)
    team: str = Field(min_length=1, max_length=200)
    points: int = Field(ge=1, le=5, strict=True)


class SlateConfig(StrictModel):
    game_ids: list[int] = Field(default_factory=list, max_length=100)
    player_ids: list[int] = Field(default_factory=list, max_length=1500)
    featured_game_id: int | None = None
    underdogs: list[Underdog] = Field(default_factory=list, max_length=100)


class ChallengeConfig(SlateConfig):
    expected_version: int = Field(ge=0)


class EntryWrite(StrictModel):
    expected_revision: int = Field(ge=0, strict=True)
    submit: bool = True
    selections: list[Selection] = Field(max_length=12)
    tiebreaker: int | None = Field(None, ge=0, le=2_147_483_647, strict=True)


class EntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    challenge_id: int
    user_id: int
    status: str
    revision: int
    selections: list[Selection]
    tiebreaker: int | None
    submitted_at: datetime | None


class PoolPlayer(BaseModel):
    id: int
    game_id: int
    name: str
    school: str
    position: str
    image_url: str | None


class ChallengeSponsorRead(BaseModel):
    name: str
    label: str
    tagline: str
    logo_url: str
    youtube_url: str
    season: int
    week: int


class ChallengeRead(BaseModel):
    experience: ExperienceRead | None = None
    participant_count: int = 0
    sponsor: ChallengeSponsorRead | None = None
    id: int
    round_id: int
    kind: ChallengeKind
    name: str
    state: str
    settlement_status: str
    version: int
    rules_version: str
    rules: str
    lock_at: datetime | None
    server_now: datetime
    published_at: datetime | None
    scoring_version: str | None
    scoring_rules: dict | None
    games: list[GameRead]
    players: list[PoolPlayer]
    featured_game_id: int | None
    underdogs: list[Underdog]
    entry: EntryRead | None
    cancellation_reason: str | None
    draft_config: SlateConfig | None = None


class RoundRead(BaseModel):
    sponsor: ChallengeSponsorRead | None = None
    id: int
    season: int
    week: int
    state: str
    next_rollover_at: datetime
    server_now: datetime
    challenges: list[ChallengeRead]


class DuelInvite(StrictModel):
    invitee_id: int = Field(gt=0)


class DuelRead(BaseModel):
    id: int
    challenge_id: int
    inviter: Participant
    invitee: Participant
    status: str
    outcome: str | None


class LeaderRow(Participant):
    rank: int
    points: int


class LeaderboardRead(BaseModel):
    week: int | None
    season: int
    round_id: int | None
    provisional: bool
    data: list[LeaderRow]
    your_rank: LeaderRow | None


class ResultRow(BaseModel):
    participant: Participant
    entry_id: int
    raw_points: float | None
    challenge_points: int | None
    rank: int | None
    status: str
    tiebreaker_error: int | None
    selections: list[Selection] | None


class ResultsRead(BaseModel):
    challenge_id: int
    state: str
    data: list[ResultRow]
    total: int
    limit: int
    offset: int
    my_result: ResultRow | None


class AdminAction(StrictModel):
    expected_version: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=500)


class ValidationRead(BaseModel):
    valid: bool
    blockers: list[str]
    lock_at: datetime | None


class ProfileRead(Participant):
    recognition: list[str]


class CatalogRead(BaseModel):
    season: int
    week: int
    games: list[GameRead]
    players: list[PoolPlayer]


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int | None
    action: str
    at: datetime
    details: dict
