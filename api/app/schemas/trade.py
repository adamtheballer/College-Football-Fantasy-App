from pydantic import BaseModel


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


class TradeProposalRequest(BaseModel):
    league_id: int
    from_team_id: int
    to_team_id: int
    give_ids: list[int]
    receive_ids: list[int]
    note: str | None = None


class TradeProposalResponse(BaseModel):
    proposal_ref: str
    message: str


class TradeOfferSummary(BaseModel):
    proposal_ref: str
    league_id: int
    from_team_id: int
    to_team_id: int
    from_user_id: int
    to_user_id: int
    status: str
    review_status: str
    review_mode: str
    note: str | None = None
    expires_at: str | None = None
    responded_at: str | None = None
    give_ids: list[int]
    receive_ids: list[int]
    created_at: str
    updated_at: str


class TradeOfferList(BaseModel):
    data: list[TradeOfferSummary]
    total: int
    limit: int
    offset: int


class TradeOfferActionResponse(BaseModel):
    proposal_ref: str
    status: str
    message: str
