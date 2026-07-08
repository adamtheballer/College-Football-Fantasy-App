from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404, require_league_member
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.watchlist import Watchlist, WatchlistPlayer
from collegefootballfantasy_api.app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistList,
    WatchlistPlayerCreate,
    WatchlistPlayerUpdate,
    WatchlistRead,
    WatchlistUpdate,
)
from collegefootballfantasy_api.app.services.watchlist_service import (
    add_watchlist_player,
    owned_watchlist_or_404,
    serialize_watchlist,
    update_watchlist_player,
)

router = APIRouter()


@router.get("", response_model=WatchlistList)
def list_watchlists_endpoint(
    league_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistList:
    if league_id is not None:
        get_league_or_404(db, league_id)
        require_league_member(db, league_id, current_user)

    query = (
        db.query(Watchlist)
        .options(joinedload(Watchlist.players).joinedload(WatchlistPlayer.player))
        .filter(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.updated_at.desc(), Watchlist.id.desc())
    )
    if league_id is not None:
        query = query.filter(Watchlist.league_id == league_id)

    rows = query.all()
    data = [
        serialize_watchlist(db, row.id, current_user=current_user)
        for row in rows
    ]
    return WatchlistList(data=data, total=len(data))


@router.post("", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED)
def create_watchlist_endpoint(
    payload: WatchlistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    if payload.league_id is not None:
        get_league_or_404(db, payload.league_id)
        require_league_member(db, payload.league_id, current_user)

    watchlist = Watchlist(user_id=current_user.id, league_id=payload.league_id, name=payload.name.strip())
    db.add(watchlist)
    db.commit()
    return serialize_watchlist(db, watchlist.id, current_user=current_user)


@router.patch("/{watchlist_id}", response_model=WatchlistRead)
def rename_watchlist_endpoint(
    watchlist_id: int,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    watchlist = owned_watchlist_or_404(db, watchlist_id, current_user)
    watchlist.name = payload.name.strip()
    db.add(watchlist)
    db.commit()
    return serialize_watchlist(db, watchlist.id, current_user=current_user)


@router.post("/{watchlist_id}/players", response_model=WatchlistRead)
def add_watchlist_player_endpoint(
    watchlist_id: int,
    payload: WatchlistPlayerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    watchlist = owned_watchlist_or_404(db, watchlist_id, current_user)
    player = db.get(Player, payload.player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    add_watchlist_player(db, watchlist=watchlist, payload=payload)
    db.commit()
    return serialize_watchlist(db, watchlist.id, current_user=current_user)


@router.patch("/{watchlist_id}/players/{player_id}", response_model=WatchlistRead)
def update_watchlist_player_endpoint(
    watchlist_id: int,
    player_id: int,
    payload: WatchlistPlayerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    watchlist = owned_watchlist_or_404(db, watchlist_id, current_user)
    row = (
        db.query(WatchlistPlayer)
        .filter(WatchlistPlayer.watchlist_id == watchlist.id, WatchlistPlayer.player_id == player_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist player not found")
    update_watchlist_player(db, row=row, payload=payload)
    db.commit()
    return serialize_watchlist(db, watchlist.id, current_user=current_user)


@router.delete("/{watchlist_id}/players/{player_id}", response_model=WatchlistRead)
def remove_watchlist_player_endpoint(
    watchlist_id: int,
    player_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WatchlistRead:
    watchlist = owned_watchlist_or_404(db, watchlist_id, current_user)
    row = (
        db.query(WatchlistPlayer)
        .filter(WatchlistPlayer.watchlist_id == watchlist.id, WatchlistPlayer.player_id == player_id)
        .first()
    )
    if row:
        db.delete(row)
        db.commit()
    return serialize_watchlist(db, watchlist.id, current_user=current_user)
