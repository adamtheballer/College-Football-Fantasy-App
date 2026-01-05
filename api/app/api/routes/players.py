from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.player import create_players, get_player, list_players
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.schemas.player import PlayerCreate, PlayerList, PlayerRead

router = APIRouter()


@router.post("", response_model=list[PlayerRead], status_code=status.HTTP_201_CREATED)
def create_players_endpoint(
    players_in: list[PlayerCreate], db: Session = Depends(get_db)
) -> list[PlayerRead]:
    return create_players(db, players_in)


@router.get("", response_model=PlayerList)
def list_players_endpoint(
    limit: int = 50,
    offset: int = 0,
    position: str | None = None,
    school: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> PlayerList:
    players, total = list_players(
        db,
        limit=limit,
        offset=offset,
        position=position,
        school=school,
        search=search,
    )
    return PlayerList(data=players, total=total, limit=limit, offset=offset)


@router.get("/{player_id}", response_model=PlayerRead)
def get_player_endpoint(player_id: int, db: Session = Depends(get_db)) -> PlayerRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return player
