from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.player import create_players, get_player, list_players
from collegefootballfantasy_api.app.crud.player_stat import get_player_stat, upsert_player_stat
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.schemas.player import PlayerCreate, PlayerList, PlayerRead
from collegefootballfantasy_api.app.schemas.player_stat import PlayerStatResponse

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
    league_id: int | None = None,
    available_only: bool = False,
    sort: str | None = None,
    db: Session = Depends(get_db),
) -> PlayerList:
    players, total = list_players(
        db,
        limit=limit,
        offset=offset,
        position=position,
        school=school,
        search=search,
        league_id=league_id,
        available_only=available_only,
        sort=sort,
    )
    return PlayerList(data=players, total=total, limit=limit, offset=offset)


@router.get("/{player_id}", response_model=PlayerRead)
def get_player_endpoint(player_id: int, db: Session = Depends(get_db)) -> PlayerRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return player


@router.get("/{player_id}/stats", response_model=PlayerStatResponse)
def get_player_stats_endpoint(
    player_id: int,
    season: int | None = None,
    week: int | None = None,
    refresh: bool = False,
    db: Session = Depends(get_db),
) -> PlayerStatResponse:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    season_value = season or datetime.now().year
    week_value = week or 1

    existing = get_player_stat(db, player_id, season_value, week_value)
    if existing and not refresh:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source=existing.source,
            cached=True,
            stats=existing.stats,
        )

    if not player.external_id:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="Player external_id is not set for SportsData lookup.",
        )

    client = SportsDataClient()
    try:
        stats = client.get_player_stats(player.external_id, season=season_value, week=week_value)
    except RuntimeError as exc:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message=str(exc),
        )

    if not stats:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="No stats returned from SportsData.",
        )

    stored = upsert_player_stat(db, player_id, season_value, week_value, stats=stats, source="sportsdata")
    return PlayerStatResponse(
        player_id=player_id,
        season=season_value,
        week=week_value,
        source=stored.source,
        cached=False,
        stats=stored.stats,
    )
