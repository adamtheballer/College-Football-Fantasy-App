from datetime import datetime

from pydantic import BaseModel


class NameChangeEligibility(BaseModel):
    account_id: int
    current_name: str
    server_time: datetime
    last_successful_change_at: datetime | None
    next_eligible_at: datetime | None
    remaining_wait_seconds: int
    can_change_name: bool
