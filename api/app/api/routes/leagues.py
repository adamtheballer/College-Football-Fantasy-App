from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.league import (
    create_league,
    delete_league,
    get_league,
    list_leagues,
    update_league,
)
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.schemas.league import LeagueCreate, LeagueList, LeagueRead, LeagueUpdate

router = APIRouter()


@router.post("", response_model=LeagueRead, status_code=status.HTTP_201_CREATED)
def create_league_endpoint(league_in: LeagueCreate, db: Session = Depends(get_db)) -> LeagueRead:
    return create_league(db, league_in)


@router.get("", response_model=LeagueList)
def list_leagues_endpoint(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> LeagueList:
    leagues, total = list_leagues(db, limit=limit, offset=offset)
    return LeagueList(data=leagues, total=total, limit=limit, offset=offset)


@router.get("/{league_id}", response_model=LeagueRead)
def get_league_endpoint(league_id: int, db: Session = Depends(get_db)) -> LeagueRead:
    league = get_league(db, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return league


@router.put("/{league_id}", response_model=LeagueRead)
def update_league_endpoint(
    league_id: int, league_in: LeagueUpdate, db: Session = Depends(get_db)
) -> LeagueRead:
    league = get_league(db, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return update_league(db, league, league_in)


@router.delete("/{league_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_league_endpoint(league_id: int, db: Session = Depends(get_db)) -> None:
    league = get_league(db, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    delete_league(db, league)
