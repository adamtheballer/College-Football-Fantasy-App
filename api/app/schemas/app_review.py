from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppReviewClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    app_version: str = Field(min_length=1, max_length=80)
    app_build: str = Field(min_length=1, max_length=80)


class AppReviewState(BaseModel):
    account_id: int
    enabled: bool
    review_request_claimed_at: datetime | None


class AppReviewClaimResult(AppReviewState):
    authorization: Literal["granted", "already_claimed", "disabled"]
