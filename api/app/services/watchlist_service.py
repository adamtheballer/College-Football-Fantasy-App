from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.watchlist import Watchlist, WatchlistPlayer
from collegefootballfantasy_api.app.schemas.watchlist import (
    WatchlistPlayerCreate,
    WatchlistPlayerRead,
    WatchlistPlayerUpdate,
    WatchlistRead,
)
from collegefootballfantasy_api.app.services.player_availability import (
    build_availability_context,
    player_availability,
)


def owned_watchlist_or_404(db: Session, watchlist_id: int, current_user: User) -> Watchlist:
    watchlist = (
        db.query(Watchlist)
        .options(joinedload(Watchlist.players).joinedload(WatchlistPlayer.player))
        .filter(Watchlist.id == watchlist_id, Watchlist.user_id == current_user.id)
        .first()
    )
    if not watchlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist not found")
    return watchlist


def _clean_tags(tags: list[str] | None) -> list[str]:
    if not tags:
        return []
    cleaned: list[str] = []
    for tag in tags:
        text = str(tag).strip().lower()
        if text and text not in cleaned:
            cleaned.append(text[:40])
    return cleaned[:12]


def _validate_priority(priority: int | None) -> int:
    value = 3 if priority is None else int(priority)
    if value < 1 or value > 5:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="priority must be between 1 and 5")
    return value


def serialize_watchlist(db: Session, watchlist_id: int, *, current_user: User | None = None) -> WatchlistRead:
    watchlist = (
        db.query(Watchlist)
        .options(joinedload(Watchlist.players).joinedload(WatchlistPlayer.player))
        .filter(Watchlist.id == watchlist_id)
        .one()
    )
    league = db.get(League, watchlist.league_id) if watchlist.league_id else None
    context = build_availability_context(db, league_id=watchlist.league_id, current_user=current_user)
    sorted_items = sorted(watchlist.players, key=lambda row: (row.priority, row.created_at, row.id))
    items = [
        WatchlistPlayerRead(
            id=item.id,
            watchlist_id=item.watchlist_id,
            team_id=item.team_id,
            player=item.player,
            availability=player_availability(db, player=item.player, league=league, context=context) if item.player else None,
            notes=item.notes,
            priority=item.priority,
            tags=_clean_tags(item.tags),
            alert_available=item.alert_available,
            alert_injury=item.alert_injury,
            alert_projection=item.alert_projection,
            alert_ownership=item.alert_ownership,
            alert_matchup=item.alert_matchup,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in sorted_items
        if item.player is not None
    ]
    return WatchlistRead(
        id=watchlist.id,
        user_id=watchlist.user_id,
        league_id=watchlist.league_id,
        name=watchlist.name,
        players=[item.player for item in sorted_items if item.player is not None],
        items=items,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
    )


def add_watchlist_player(
    db: Session,
    *,
    watchlist: Watchlist,
    payload: WatchlistPlayerCreate,
) -> WatchlistPlayer:
    player = db.get(Player, payload.player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    if payload.team_id is not None:
        team = db.get(Team, payload.team_id)
        if not team or team.league_id != watchlist.league_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="team_id is not in this league")

    existing = (
        db.query(WatchlistPlayer)
        .filter(WatchlistPlayer.watchlist_id == watchlist.id, WatchlistPlayer.player_id == payload.player_id)
        .first()
    )
    if existing:
        return update_watchlist_player(db, row=existing, payload=WatchlistPlayerUpdate(**payload.model_dump()))

    row = WatchlistPlayer(
        watchlist_id=watchlist.id,
        team_id=payload.team_id,
        player_id=payload.player_id,
        notes=payload.notes.strip() if payload.notes else None,
        priority=_validate_priority(payload.priority),
        tags=_clean_tags(payload.tags),
        alert_available=payload.alert_available,
        alert_injury=payload.alert_injury,
        alert_projection=payload.alert_projection,
        alert_ownership=payload.alert_ownership,
        alert_matchup=payload.alert_matchup,
    )
    db.add(row)
    return row


def update_watchlist_player(
    db: Session,
    *,
    row: WatchlistPlayer,
    payload: WatchlistPlayerUpdate,
) -> WatchlistPlayer:
    if payload.team_id is not None:
        team = db.get(Team, payload.team_id)
        watchlist = db.get(Watchlist, row.watchlist_id)
        if not team or not watchlist or team.league_id != watchlist.league_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="team_id is not in this league")
        row.team_id = payload.team_id
    if payload.notes is not None:
        row.notes = payload.notes.strip() or None
    if payload.priority is not None:
        row.priority = _validate_priority(payload.priority)
    if payload.tags is not None:
        row.tags = _clean_tags(payload.tags)
    for field in ("alert_available", "alert_injury", "alert_projection", "alert_ownership", "alert_matchup"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)
    db.add(row)
    return row
