from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.career import CareerEventsRead, CareerLeaguesRead, CareerProfileRead, CareerPublicProfileRead, CareerTrophiesRead
from collegefootballfantasy_api.app.services.career_profile import build_career_profile, build_public_career_profile, list_career_events, list_career_leagues, list_career_trophies

router = APIRouter()


@router.get("/me/career", response_model=CareerProfileRead)
def get_my_career(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CareerProfileRead:
    return build_career_profile(db, current_user)


@router.get("/me/career/history", response_model=CareerEventsRead)
def get_my_career_history(limit: int = 50, offset: int = 0, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CareerEventsRead:
    rows, total = list_career_events(db, current_user.id, limit=max(1, min(limit, 100)), offset=max(0, offset))
    return CareerEventsRead(data=rows, total=total)


@router.get("/me/career/leagues", response_model=CareerLeaguesRead)
def get_my_career_leagues(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CareerLeaguesRead:
    return CareerLeaguesRead(data=list_career_leagues(db, current_user.id))


@router.get("/me/career/trophies", response_model=CareerTrophiesRead)
def get_my_career_trophies(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> CareerTrophiesRead:
    return CareerTrophiesRead(data=list_career_trophies(db, current_user.id))


@router.get("/{user_id}/career", response_model=CareerPublicProfileRead)
def get_public_career(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CareerPublicProfileRead:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return build_public_career_profile(db, user)
