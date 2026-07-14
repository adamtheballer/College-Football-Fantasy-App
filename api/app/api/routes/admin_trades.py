from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.trade_service import process_trade_offers_once

router = APIRouter()


@router.post("/process-due", response_model=dict[str, int])
def process_due_trades_endpoint(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin_user),
) -> dict[str, int]:
    return process_trade_offers_once(db)
