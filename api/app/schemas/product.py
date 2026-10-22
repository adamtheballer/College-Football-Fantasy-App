from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

EventKind = Literal['session', 'challenge_view', 'challenge_start', 'challenge_submit', 'challenge_share', 'guide_complete', 'notification_open']

class ProductEventCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    kind: EventKind
    challenge_id: int | None = Field(None, gt=0)
    platform: Literal['web', 'ios', 'android'] = 'web'
    app_version: str | None = Field(None, max_length=40, pattern=r'^[A-Za-z0-9._-]+$')
    app_build: str | None = Field(None, max_length=40, pattern=r'^[A-Za-z0-9._-]+$')

class ProductEventReceipt(BaseModel):
    recorded: bool

class HomeAction(BaseModel):
    key: str
    title: str
    detail: str
    href: str
    priority: int
    deadline: datetime | None = None

class HomeActions(BaseModel):
    data: list[HomeAction]
    checked_at: datetime

class ParticipationMetrics(BaseModel):
    days: int
    accounts: int
    new_accounts_in_leagues: int
    active_accounts: int
    returning_accounts: int
    guide_finished_accounts: int
    challenge_viewers: int
    challenge_starters: int
    challenge_submitters: int
    submitted_entries: int
    sharers: int
    notification_openers: int
    review_authorizations: int
    review_invocations: int
    native_versions: dict[str, int]
    excluded_test_and_admin: bool = True
    events_since: datetime | None
    note: str = 'Views, starts and sessions begin with this release; entries use the authoritative submission ledger. Review invocation does not mean Apple displayed a sheet or received a rating.'

class PlayerHealth(BaseModel):
    season: int
    week: int | None
    checked_at: datetime
    verified_players: int
    awaiting_stats_or_participation: int
    latest_fact_at: datetime | None
    latest_reviewed_injury_at: datetime | None
    injury_feed_status: Literal["current", "stale", "unknown", "offseason"]
    injury_sources: dict[str,str]
    invalid_fact_count: int
    feed_gap_count: int
    sample_player_ids: list[int]
    status: Literal['healthy', 'attention', 'pending']
    note: str = 'An absent box score does not establish participation or a zero score.'
