from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.api.deps import get_optional_current_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.player_rankings import PlayerRankings, PlayerLeaders, PositionLeader
from collegefootballfantasy_api.app.services.player_rankings import ranking_rows
from collegefootballfantasy_api.app.services.player_pool_filters import ELIGIBLE_FANTASY_POSITIONS

router = APIRouter()


@router.get("", response_model=PlayerRankings)
def rankings(season: int = Query(default=settings.current_season_year, ge=2020, le=2100),
             period: Literal["week", "season"] = "week", week: int | None = Query(None, ge=1, le=15),
             position: Literal["QB", "RB", "WR", "TE", "K"] | None = None,
             league_id: int | None = Query(None, ge=1), mine: bool = False,
             search: str = Query("", max_length=100), limit: int = Query(50, ge=1, le=100),
             offset: int = Query(0, ge=0), db: Session = Depends(get_db),
             user: User | None = Depends(get_optional_current_user)) -> PlayerRankings:
    if mine and league_id is None:
        raise HTTPException(422, "Select a league to view your players.")
    context, rows = ranking_rows(db, season=season, period=period, week=week, league_id=league_id, user=user)
    term = search.strip().casefold()
    rows = [r for r in rows if (not position or r.position == position)
            and (not mine or r.on_my_roster) and (not term or term in f"{r.name} {r.school}".casefold())]
    return PlayerRankings(**context.model_dump(), data=rows[offset:offset + limit], total=len(rows), limit=limit, offset=offset)


@router.get("/leaders", response_model=PlayerLeaders)
def leaders(season: int = Query(default=settings.current_season_year, ge=2020, le=2100),
            period: Literal["week", "season"] = "week", week: int | None = Query(None, ge=1, le=15),
            league_id: int | None = Query(None, ge=1), db: Session = Depends(get_db),
            user: User | None = Depends(get_optional_current_user)) -> PlayerLeaders:
    context, rows = ranking_rows(db, season=season, period=period, week=week, league_id=league_id, user=user)
    return PlayerLeaders(**context.model_dump(), data=[PositionLeader(position=p,
        player=next((r for r in rows if r.position == p and r.status == "final"), None)) for p in ELIGIBLE_FANTASY_POSITIONS])
