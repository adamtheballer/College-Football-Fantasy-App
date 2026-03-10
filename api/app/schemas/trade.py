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
