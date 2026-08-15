from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.trade_service import process_trade_offers_once

router = APIRouter()


@router.post("/process-due", response_model=dict[str, int])
def process_due_trades_endpoint(
    as_of: datetime | None = None,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin_user),
) -> dict[str, int]:
    # Time travel is intentionally unavailable in development and every
    # deployable runtime. The disposable browser suite uses it to advance a
    # real PostgreSQL offer from accepted_pending to its legal Monday window
    # through the same canonical processor used by the lifecycle worker.
    if as_of is not None and not settings.e2e_lifecycle_time_travel_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="lifecycle time travel is available only in the E2E runtime",
        )
    return process_trade_offers_once(db, now=as_of)
