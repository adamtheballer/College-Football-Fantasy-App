from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.api.deps import require_verified_user, require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.product import ProductEventCreate, ProductEventReceipt, HomeActions, ParticipationMetrics, PlayerHealth
from collegefootballfantasy_api.app.services.product import record_event, metrics
from collegefootballfantasy_api.app.services.home_actions import home_actions
from collegefootballfantasy_api.app.services.player_data_health import player_health

router = APIRouter()

@router.post('/events', response_model=ProductEventReceipt)
def event(payload: ProductEventCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    if request.headers.get('x-cffb-challenge-account') != str(user.id):
        raise HTTPException(409, 'analytics account changed')
    return ProductEventReceipt(recorded=record_event(db,user,payload,do_not_track=request.headers.get('dnt') == '1'))

@router.get('/home-actions', response_model=HomeActions)
def actions(db: Session = Depends(get_db), user: User = Depends(require_verified_user)):
    return home_actions(db,user.id)

@router.get('/admin/participation', response_model=ParticipationMetrics)
def participation(days: int = Query(7,ge=1,le=90), include_test_accounts: bool = False, db: Session = Depends(get_db), admin: User = Depends(require_admin_user)):
    return metrics(db, days, include_test_accounts)

@router.get('/admin/player-health', response_model=PlayerHealth)
def health(season: int = Query(settings.current_season_year,ge=2000,le=2100), db: Session = Depends(get_db), admin: User = Depends(require_admin_user)):
    return player_health(db,season)
