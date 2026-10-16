from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReleaseNoticeClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReleaseNoticeResult(BaseModel):
    account_id: int
    release_key: Literal["1.03"]
    authorization: Literal["granted", "already_seen"]
    claimed_at: datetime
