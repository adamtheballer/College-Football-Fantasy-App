from datetime import datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TradeAnalyzeRequest(BaseModel):
    receive_ids: list[int]
    give_ids: list[int]
    season: int
    week: int
    league_id: int | None = None
    league_size: int = 12
    roster_slots: dict[str, int] | None = None


class TradeAnalyzeResponse(BaseModel):
    receive_value: float | None = None
    give_value: float | None = None
    delta: float | None = None
    verdict: str
    unavailable_player_ids: list[int] = []


class TradeOfferItemCreate(BaseModel):
    team_id: int
    player_id: int | None = None
    draft_pick_id: int | None = None

    @model_validator(mode="after")
    def validate_item(self) -> "TradeOfferItemCreate":
        if self.player_id is None and self.draft_pick_id is None:
            raise ValueError("trade item requires a player_id or draft_pick_id")
        return self


class TradeOfferCreate(BaseModel):
    proposing_team_id: int
    receiving_team_id: int
    give_items: list[TradeOfferItemCreate] = Field(default_factory=list)
    receive_items: list[TradeOfferItemCreate] = Field(default_factory=list)
    message: str | None = Field(default=None, max_length=1000)
    client_request_id: str | None = Field(default=None, max_length=100)

    @field_validator("client_request_id")
    @classmethod
    def validate_client_request_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,100}", normalized):
            raise ValueError("client_request_id has an unsupported format")
        return normalized

    @model_validator(mode="after")
    def validate_sides(self) -> "TradeOfferCreate":
        if not self.give_items or not self.receive_items:
            raise ValueError("trade offer requires players from both teams")
        keys = [(item.team_id, item.player_id, item.draft_pick_id) for item in [*self.give_items, *self.receive_items]]
        if len(keys) != len(set(keys)):
            raise ValueError("trade offer cannot contain duplicate items")
        give_player_ids = {item.player_id for item in self.give_items if item.player_id is not None}
        receive_player_ids = {item.player_id for item in self.receive_items if item.player_id is not None}
        if give_player_ids & receive_player_ids:
            raise ValueError("a player cannot appear on both sides of a trade")
        return self


class TradeOfferCounterCreate(TradeOfferCreate):
    pass


class TradeActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class TradeOfferItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_offer_id: int
    team_id: int
    player_id: int | None
    draft_pick_id: int | None
    item_type: str
    player_name: str | None = None
    player_position: str | None = None
    player_school: str | None = None


class TradeReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_offer_id: int
    reviewer_user_id: int | None
    action: str
    reason: str | None
    created_at: datetime


class TradeOfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    league_id: int
    proposing_team_id: int
    receiving_team_id: int
    created_by_user_id: int | None
    status: str
    message: str | None
    accepted_at: datetime | None
    process_after: datetime | None
    processed_at: datetime | None
    expires_at: datetime | None
    failure_reason: str | None
    countered_from_trade_id: int | None
    created_at: datetime
    updated_at: datetime
    items: list[TradeOfferItemRead]
    reviews: list[TradeReviewRead] = Field(default_factory=list)


class TradeOfferList(BaseModel):
    data: list[TradeOfferRead]
    total: int
