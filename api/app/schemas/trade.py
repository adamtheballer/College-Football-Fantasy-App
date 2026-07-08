from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TradeAnalyzeRequest(BaseModel):
    receive_ids: list[int]
    give_ids: list[int]
    season: int
    week: int
    league_size: int = 12
    roster_slots: dict[str, int] | None = None


class TradeAnalyzeResponse(BaseModel):
    receive_value: float
    give_value: float
    delta: float
    verdict: str


class TradeOfferItemCreate(BaseModel):
    player_id: int | None = None
    draft_pick_id: int | None = None


class TradeOfferCreate(BaseModel):
    proposing_team_id: int
    receiving_team_id: int
    proposing_items: list[TradeOfferItemCreate] = Field(default_factory=list)
    receiving_items: list[TradeOfferItemCreate] = Field(default_factory=list)
    message: str | None = None
    expires_at: datetime | None = None


class TradeActionRequest(BaseModel):
    reason: str | None = None


class TradeCounterRequest(TradeOfferCreate):
    reason: str | None = None


class TradeOfferItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_offer_id: int
    team_id: int
    player_id: int | None = None
    draft_pick_id: int | None = None


class TradeReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_offer_id: int
    reviewer_user_id: int | None = None
    action: str
    reason: str | None = None
    created_at: datetime


class TradeOfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    proposing_team_id: int
    receiving_team_id: int
    status: str
    expires_at: datetime | None = None
    message: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime
    items: list[TradeOfferItemRead] = []
    reviews: list[TradeReviewRead] = []


class TradeOfferList(BaseModel):
    data: list[TradeOfferRead]
    total: int
