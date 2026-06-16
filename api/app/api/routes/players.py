from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.app.api.deps import get_current_user
from api.app.core.config import settings
from api.app.crud.player import create_players, get_player, list_players
from api.app.crud.player_stat import get_player_stat, upsert_player_stat
from api.app.db.session import get_db
from api.app.integrations.sportsdata import SportsDataClient
from api.app.models.player_stat import PlayerStat
from api.app.schemas.player import PlayerCreate, PlayerList, PlayerRead
from api.app.schemas.player_stat import PlayerSeasonSummaryResponse, PlayerSeasonTotals, PlayerStatResponse
from api.app.services.provider_cache import ensure_feed_fresh
from api.app.services.player_news import build_player_latest_news

router = APIRouter()


def _is_stale(updated_at: datetime | None, ttl_days: int) -> bool:
    if not updated_at:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return updated_at <= now - timedelta(days=max(1, ttl_days))


def _stat_value(stats: dict, keys: list[str]) -> float:
    for key in keys:
        value = stats.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


@router.post("", response_model=list[PlayerRead], status_code=status.HTTP_201_CREATED)
def create_players_endpoint(
    players_in: list[PlayerCreate],
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> list[PlayerRead]:
    if settings.environment.lower() == "production":
        get_current_user(db=db, authorization=authorization)
    return create_players(db, players_in)


@router.get("", response_model=PlayerList)
def list_players_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    position: str | None = None,
    school: str | None = None,
    search: str | None = None,
    league_id: int | None = None,
    available_in_league_id: int | None = None,
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
        available_in_league_id=available_in_league_id,
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
    stale = _is_stale(existing.updated_at, settings.sportsdata_cache_ttl_days) if existing else True
    should_refresh = refresh or not existing or stale

    if existing and not should_refresh:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source=existing.source,
            cached=True,
            stats=existing.stats,
        )

    if not player.external_id and not existing:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="Player external_id is not set for SportsData lookup.",
        )

    def _refresh_from_provider() -> None:
        if not player.external_id:
            raise RuntimeError("Player external_id is not set for SportsData lookup.")
        client = SportsDataClient()
        stats = client.get_player_stats(player.external_id, season=season_value, week=week_value)
        if not stats:
            raise RuntimeError("No stats returned from SportsData.")
        upsert_player_stat(db, player_id, season_value, week_value, stats=stats, source="sportsdata")

    refreshed = False
    stale_fallback_message: str | None = None
    if should_refresh:
        try:
            refreshed, _state = ensure_feed_fresh(
                db,
                provider="sportsdata",
                feed="player_game_stats_week",
                scope={
                    "player_id": player.id,
                    "external_id": player.external_id,
                    "season": season_value,
                    "week": week_value,
                },
                refresh_fn=_refresh_from_provider,
                ttl_days=settings.sportsdata_cache_ttl_days,
                force_refresh=refresh or stale or not existing,
            )
            db.commit()
        except RuntimeError as exc:
            if not existing:
                return PlayerStatResponse(
                    player_id=player_id,
                    season=season_value,
                    week=week_value,
                    source="sportsdata",
                    cached=False,
                    stats=None,
                    message=str(exc),
                )
            stale_fallback_message = f"Using stale cached stats: {exc}"
        except Exception as exc:
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"SportsData refresh failed: {exc}",
                ) from exc
            stale_fallback_message = f"Using stale cached stats: {exc}"

    stored = get_player_stat(db, player_id, season_value, week_value) or existing
    if not stored:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="No stats available.",
        )
    return PlayerStatResponse(
        player_id=player_id,
        season=season_value,
        week=week_value,
        source=stored.source,
        cached=not refreshed,
        stats=stored.stats,
        message=stale_fallback_message,
    )


@router.get("/{player_id}/season-summary", response_model=PlayerSeasonSummaryResponse)
def get_player_season_summary_endpoint(
    player_id: int,
    season: int = 2025,
    db: Session = Depends(get_db),
) -> PlayerSeasonSummaryResponse:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    stat_rows = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id, PlayerStat.season == season, PlayerStat.week > 0)
        .order_by(PlayerStat.week.asc())
        .all()
    )

    source = "sportsdata_cached"
    message: str | None = None
    if not stat_rows:
        source = "unavailable"
        message = "No cached season stats were found for this player yet."

    totals_map = {
        "passing_completions": 0.0,
        "passing_attempts": 0.0,
        "passing_yards": 0.0,
        "passing_tds": 0.0,
        "interceptions": 0.0,
        "rushing_attempts": 0.0,
        "rushing_yards": 0.0,
        "rushing_tds": 0.0,
        "receptions": 0.0,
        "receiving_yards": 0.0,
        "receiving_tds": 0.0,
        "field_goals_made": 0.0,
        "extra_points_made": 0.0,
    }

    for row in stat_rows:
        stats = row.stats or {}
        totals_map["passing_completions"] += _stat_value(stats, ["PassingCompletions", "Completions", "PassCompletions"])
        totals_map["passing_attempts"] += _stat_value(stats, ["PassingAttempts", "Attempts", "PassAttempts"])
        totals_map["passing_yards"] += _stat_value(stats, ["PassingYards", "PassYards"])
        totals_map["passing_tds"] += _stat_value(stats, ["PassingTouchdowns", "PassTD", "PassingTDs"])
        totals_map["interceptions"] += _stat_value(stats, ["Interceptions", "INT", "Ints"])
        totals_map["rushing_attempts"] += _stat_value(stats, ["RushingAttempts", "RushAttempts", "Carries"])
        totals_map["rushing_yards"] += _stat_value(stats, ["RushingYards", "RushYards"])
        totals_map["rushing_tds"] += _stat_value(stats, ["RushingTouchdowns", "RushTD", "RushingTDs"])
        totals_map["receptions"] += _stat_value(stats, ["Receptions", "Rec"])
        totals_map["receiving_yards"] += _stat_value(stats, ["ReceivingYards", "RecYards"])
        totals_map["receiving_tds"] += _stat_value(stats, ["ReceivingTouchdowns", "RecTD", "ReceivingTDs"])
        totals_map["field_goals_made"] += _stat_value(stats, ["FieldGoalsMade", "FieldGoals", "FGM"])
        totals_map["extra_points_made"] += _stat_value(stats, ["ExtraPointsMade", "ExtraPoints", "XPM"])

    games_count = (
        db.query(func.count(func.distinct(PlayerStat.week)))
        .filter(PlayerStat.player_id == player_id, PlayerStat.season == season, PlayerStat.week > 0)
        .scalar()
        or 0
    )

    attempts = totals_map["passing_attempts"]
    completions = totals_map["passing_completions"]
    rushing_attempts = totals_map["rushing_attempts"]
    receptions = totals_map["receptions"]
    completion_pct = round((completions / attempts) * 100.0, 1) if attempts > 0 else None
    yards_per_carry = round(totals_map["rushing_yards"] / rushing_attempts, 2) if rushing_attempts > 0 else None
    yards_per_reception = round(totals_map["receiving_yards"] / receptions, 2) if receptions > 0 else None

    fantasy_points = (
        totals_map["passing_yards"] / 25.0
        + totals_map["passing_tds"] * 4.0
        - totals_map["interceptions"] * 2.0
        + totals_map["rushing_yards"] / 10.0
        + totals_map["rushing_tds"] * 6.0
        + totals_map["receptions"] * 1.0
        + totals_map["receiving_yards"] / 10.0
        + totals_map["receiving_tds"] * 6.0
        + totals_map["field_goals_made"] * 3.0
        + totals_map["extra_points_made"] * 1.0
    )

    totals = PlayerSeasonTotals(
        games=int(games_count),
        passing_completions=round(totals_map["passing_completions"], 1),
        passing_attempts=round(totals_map["passing_attempts"], 1),
        passing_yards=round(totals_map["passing_yards"], 1),
        passing_tds=round(totals_map["passing_tds"], 1),
        interceptions=round(totals_map["interceptions"], 1),
        rushing_attempts=round(totals_map["rushing_attempts"], 1),
        rushing_yards=round(totals_map["rushing_yards"], 1),
        rushing_tds=round(totals_map["rushing_tds"], 1),
        receptions=round(totals_map["receptions"], 1),
        receiving_yards=round(totals_map["receiving_yards"], 1),
        receiving_tds=round(totals_map["receiving_tds"], 1),
        field_goals_made=round(totals_map["field_goals_made"], 1),
        extra_points_made=round(totals_map["extra_points_made"], 1),
        completion_pct=completion_pct,
        yards_per_carry=yards_per_carry,
        yards_per_reception=yards_per_reception,
        fantasy_points=round(fantasy_points, 1),
    )

    latest_news_result = build_player_latest_news(
        db,
        player=player,
        season=season,
        totals=totals,
    )

    return PlayerSeasonSummaryResponse(
        player_id=player_id,
        season=season,
        source=source,
        totals=totals,
        latest_news=latest_news_result.text,
        latest_news_source_type=latest_news_result.source_type,
        latest_news_sources=latest_news_result.sources,
        latest_news_verified_at=latest_news_result.verified_at,
        message=message,
    )
