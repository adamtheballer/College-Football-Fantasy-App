"""Unlisted future-only preview. Writes commit once under a league lock."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, require_admin_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.dynasty import (
    DynastyFranchise,
    DynastySeason,
)
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.dynasty import (
    DynastyCatalogInput,
    DynastyClose,
    DynastyCreate,
    DynastyJoin,
    DynastyList,
    DynastyPool,
    DynastySelection,
    DynastyState,
    DynastyTradeCreate,
)
from collegefootballfantasy_api.app.services import dynasty as service


def require_preview():
    if not settings.dynasty_preview_enabled or (
        settings.is_production and settings.current_season_year < 2027
    ):
        raise HTTPException(status_code=404, detail="not found")


router = APIRouter(dependencies=[Depends(require_preview)])


def transaction(db: Session, action):
    try:
        result = action()
        db.flush()
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="dynasty state changed; refresh and retry"
        ) from exc
    except Exception:
        db.rollback()
        raise


@router.get("/capabilities")
def capabilities(user: User = Depends(get_current_user)):
    return {"enabled": True, "earliest_season": 2027, "preview": True}


@router.post("/catalog")
def catalog(
    payload: DynastyCatalogInput,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin_user),
):
    transaction(db, lambda: service.review_catalog(db, payload.data))
    return {"reviewed": len(payload.data)}


@router.get("/leagues", response_model=DynastyList)
def leagues(
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ids = db.scalars(
        select(DynastyFranchise.league_id)
        .where(DynastyFranchise.owner_user_id == user.id)
        .order_by(DynastyFranchise.league_id.desc())
        .offset(offset)
        .limit(limit)
    )
    return DynastyList(data=[service.state(db, lid, user) for lid in ids])


@router.post("/leagues", response_model=DynastyState, status_code=201)
def create(
    payload: DynastyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lid = transaction(db, lambda: service.create_league(db, user, payload))
    return service.state(db, lid, user)


@router.post("/join", response_model=DynastyState)
def join(
    payload: DynastyJoin,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lid = transaction(
        db,
        lambda: service.join_league(db, user, payload.invite_code, payload.team_name),
    )
    return service.state(db, lid, user)


@router.get("/leagues/{league_id}", response_model=DynastyState)
def detail(
    league_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return service.state(db, league_id, user)


@router.get("/leagues/{league_id}/history/{season_year}")
def history(
    league_id: int,
    season_year: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service.context(db, league_id, user)
    row = db.get(DynastySeason, (league_id, season_year))
    if row is None or row.status != "closed":
        raise HTTPException(status_code=404, detail="closed season not found")
    return {
        "season": row.season,
        "results": row.results_json,
        "rosters": row.roster_snapshot_json,
        "order": row.order_json,
    }


@router.get("/leagues/{league_id}/pool", response_model=DynastyPool)
def pool(
    league_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    config, _, season = service.context(db, league_id, user)
    rows = service.pool(db, config, season)
    return DynastyPool(
        data=rows[offset : offset + limit], total=len(rows), limit=limit, offset=offset
    )


def mutate(db, lid, user, action):
    def operation():
        config, league, season = service.context(db, lid, user, write=True)
        action(config, league, season)

    transaction(db, operation)
    return service.state(db, lid, user)


@router.post("/leagues/{league_id}/start", response_model=DynastyState)
def start(
    league_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(db, league_id, user, lambda c, l, s: service.start(db, c, l, s, user))


@router.post("/leagues/{league_id}/picks/{pick_id}", response_model=DynastyState)
def pick(
    league_id: int,
    pick_id: int,
    payload: DynastySelection,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(
        db,
        league_id,
        user,
        lambda c, l, s: service.pick(db, c, s, pick_id, payload.player_id, user),
    )


@router.post(
    "/leagues/{league_id}/trades", response_model=DynastyState, status_code=201
)
def trade(
    league_id: int,
    payload: DynastyTradeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(
        db, league_id, user, lambda c, l, s: service.propose_trade(db, c, payload, user)
    )


@router.post(
    "/leagues/{league_id}/trades/{trade_id}/{action}", response_model=DynastyState
)
def settle(
    league_id: int,
    trade_id: int,
    action: Literal["accept", "cancel", "reject"],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(
        db,
        league_id,
        user,
        lambda c, l, s: service.settle_trade(db, c, trade_id, action, user),
    )


@router.post(
    "/leagues/{league_id}/rosters/{entry_id}/drop", response_model=DynastyState
)
def drop(
    league_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(
        db, league_id, user, lambda c, l, s: service.drop(db, c, s, entry_id, user)
    )


@router.post("/leagues/{league_id}/close", response_model=DynastyState)
def close(
    league_id: int,
    payload: DynastyClose,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(
        db,
        league_id,
        user,
        lambda c, l, s: service.close_season(db, c, l, s, user, payload.results),
    )


@router.post("/leagues/{league_id}/rollover", response_model=DynastyState)
def rollover(
    league_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return mutate(
        db, league_id, user, lambda c, l, s: service.rollover(db, c, l, s, user)
    )
