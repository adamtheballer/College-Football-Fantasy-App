from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class MembershipFeatures(BaseModel):
    unlimited_leagues: bool
    dynasty: bool
    player_pictures: bool
    weekly_challenges: bool
    live_refresh_seconds: int


class FreeLeagueRead(BaseModel):
    id: int
    name: str
    selected: bool


class FreeLeagueChoice(BaseModel):
    league_ids: list[int] = Field(min_length=1, max_length=2)


class MembershipRead(BaseModel):
    plan: Literal["free", "pro"]
    active: bool
    launch_at: datetime | None
    enforcement_active: bool
    amount_cents: int = 1000
    currency: str = "usd"
    interval: str = "year"
    expires_at: datetime | None
    source: str | None
    cancel_at_period_end: bool
    league_limit: int | None
    league_count: int
    free_leagues: list[FreeLeagueRead]
    free_league_choice_locked: bool
    features: MembershipFeatures
    web_checkout_ready: bool
    apple_purchase_ready: bool
    apple_product_id: str | None
    apple_account_token: str | None
    has_stripe_customer: bool


class MembershipUrl(BaseModel):
    url: str


class ApplePurchaseInput(BaseModel):
    signed_transaction: str = Field(min_length=20, max_length=30000)


class AppleNotificationInput(BaseModel):
    signedPayload: str = Field(min_length=20, max_length=60000)
