from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.api.deps import get_optional_current_user, require_admin_user
from collegefootballfantasy_api.app.crud.player import create_players, get_player, list_players
from collegefootballfantasy_api.app.crud.player_stat import get_player_stat, upsert_player_stat
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_news_event import PlayerNewsEvent
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.player import (
    PlayerCardAboutRead,
    PlayerCardInjuryRead,
    PlayerCardNewsRead,
    PlayerCardRead,
    PlayerSeasonOutlookRead,
    PlayerCardStatRowRead,
    PlayerCreate,
    PlayerList,
    PlayerRead,
)
from collegefootballfantasy_api.app.schemas.historical_stats import PlayerHistoricalStatsResponse
from collegefootballfantasy_api.app.schemas.game_log import PlayerGameLogRead
from collegefootballfantasy_api.app.schemas.player_stat import PlayerStatResponse
from collegefootballfantasy_api.app.schemas.player_trade_value import PlayerTradeValueHistoryRead
from collegefootballfantasy_api.app.schemas.player_trajectory import PlayerTrajectoryRead
from collegefootballfantasy_api.app.services.espn_player_lookup import (
    persist_espn_player_profile,
    resolve_espn_player_by_name,
)
from collegefootballfantasy_api.app.services.historical_stats import (
    fetch_and_store_player_history,
    get_player_historical_stats_response,
    resolve_espn_player_id,
)
from collegefootballfantasy_api.app.services.player_game_log import build_player_game_log
from collegefootballfantasy_api.app.services.player_trade_value import get_player_trade_values
from collegefootballfantasy_api.app.services.player_trajectory import build_player_trajectory
from collegefootballfantasy_api.app.services.player_season_outlook import get_persisted_player_season_outlook
from collegefootballfantasy_api.app.services.provider_cache import ensure_feed_fresh
from collegefootballfantasy_api.app.services.auth_security import enforce_auth_rate_limit
from collegefootballfantasy_api.app.services.injury_status import (
    is_current_injury_designation,
    normalize_injury_status,
)
from collegefootballfantasy_api.app.services.player_pool_filters import is_retired_canonical_preseason_player

router = APIRouter()


@router.get("/{player_id}/trade-values", response_model=PlayerTradeValueHistoryRead)
def get_player_trade_values_endpoint(
    player_id: int,
    season: int = Query(default=2026, ge=2020, le=2100),
    db: Session = Depends(get_db),
) -> PlayerTradeValueHistoryRead:
    if db.get(Player, player_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return get_player_trade_values(db, player_id=player_id, season=season)


@router.get("/{player_id}/trajectory", response_model=PlayerTrajectoryRead)
def get_player_trajectory_endpoint(
    player_id: int,
    season: int = Query(default=2026, ge=2020, le=2100),
    league_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> PlayerTrajectoryRead:
    try:
        return build_player_trajectory(db, player_id=player_id, season=season, league_id=league_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _espn_player_id(external_id: str | None) -> str | None:
    if not external_id:
        return None
    normalized = str(external_id).strip()
    if not normalized:
        return None
    if normalized.lower().startswith("espn:"):
        return normalized.split(":", 1)[1].strip() or None
    return normalized if normalized.isdecimal() else None


def _profile_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _birthplace(athlete: dict) -> str | None:
    birth_place = athlete.get("birthPlace")
    if isinstance(birth_place, dict):
        parts = [
            _profile_text(birth_place.get("city")),
            _profile_text(birth_place.get("state")),
            _profile_text(birth_place.get("country")),
        ]
        return ", ".join(part for part in parts if part) or None
    if isinstance(birth_place, str):
        return _profile_text(birth_place)
    parts = [
        _profile_text(athlete.get("birthCity")),
        _profile_text(athlete.get("birthState")),
        _profile_text(athlete.get("birthCountry")),
    ]
    return ", ".join(part for part in parts if part) or None


def _preferred_bio_value(*values: object) -> str | None:
    """Use ESPN enrichment when present, otherwise the sealed identity source.

    The production player registry imports height, weight, and birthplace from
    the reviewed identity workbook.  ESPN profile enrichment is optional for
    beta, so a missing provider refresh must not make those verified fields
    disappear from a player card.
    """

    for value in values:
        text = _profile_text(value)
        if text:
            return text
    return None


def _about_source(stored_player: Player) -> str:
    if stored_player.espn_profile_synced_at:
        return "espn"
    if any((stored_player.sheet_bio_height, stored_player.sheet_bio_weight, stored_player.sheet_bio_birthplace)):
        return "verified_sheet"
    return "local"


def _map_espn_about(
    stored_player: Player,
    player: PlayerRead,
    payload: dict | None,
    message: str | None = None,
    espn_player_id: str | None = None,
) -> PlayerCardAboutRead:
    athlete = payload.get("athlete") if isinstance(payload, dict) else None
    if not isinstance(athlete, dict):
        return PlayerCardAboutRead(
            espn_player_id=espn_player_id or _espn_player_id(player.external_id),
            height=_preferred_bio_value(stored_player.espn_height, stored_player.sheet_bio_height),
            weight=_preferred_bio_value(stored_player.espn_weight, stored_player.sheet_bio_weight),
            player_class=player.player_class,
            birthplace=_preferred_bio_value(stored_player.espn_birthplace, stored_player.sheet_bio_birthplace),
            status=stored_player.espn_status or "Active",
            jersey=stored_player.espn_jersey,
            position=player.position,
            team=player.school,
            headshot_url=(stored_player.espn_headshot_url or player.image_url)
            if settings.player_headshots_enabled
            else None,
            source=_about_source(stored_player),
            message=message,
        )
    status = athlete.get("status") if isinstance(athlete.get("status"), dict) else {}
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    headshot = athlete.get("headshot") if isinstance(athlete.get("headshot"), dict) else {}
    return PlayerCardAboutRead(
        espn_player_id=_profile_text(athlete.get("id")) or espn_player_id or _espn_player_id(player.external_id),
        height=_preferred_bio_value(athlete.get("displayHeight"), stored_player.espn_height, stored_player.sheet_bio_height),
        weight=_preferred_bio_value(athlete.get("displayWeight"), stored_player.espn_weight, stored_player.sheet_bio_weight),
        player_class=player.player_class,
        birthplace=_preferred_bio_value(_birthplace(athlete), stored_player.espn_birthplace, stored_player.sheet_bio_birthplace),
        status=_profile_text(status.get("name") or status.get("abbreviation")) or stored_player.espn_status or "Active",
        jersey=_profile_text(athlete.get("jersey")) or stored_player.espn_jersey,
        position=_profile_text(position.get("displayName") or position.get("abbreviation")) or player.position,
        team=_profile_text(team.get("displayName") or team.get("shortDisplayName")) or player.school,
        headshot_url=(
            _profile_text(headshot.get("href")) or stored_player.espn_headshot_url or player.image_url
        )
        if settings.player_headshots_enabled
        else None,
        source="espn",
        message=message,
    )


def _is_stale(updated_at: datetime | None, ttl_days: int) -> bool:
    if not updated_at:
        return True
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return updated_at <= now - timedelta(days=max(1, ttl_days))


def _as_utc_timestamp(value: datetime | None) -> datetime | None:
    """Keep the public card timestamp unambiguous across database drivers."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _player_card_player_with_sheet_projection_fallback(db: Session, player: Player) -> PlayerRead:
    player_read = PlayerRead.model_validate(player)
    if player_read.sheet_projection_stats and player_read.sheet_projected_season_points is not None:
        return player_read

    sheet_player = (
        db.query(Player)
        .filter(
            Player.id != player.id,
            func.lower(Player.name) == player.name.lower(),
            func.lower(Player.school) == player.school.lower(),
            func.upper(Player.position) == player.position.upper(),
            Player.sheet_projection_stats.isnot(None),
        )
        .order_by(Player.sheet_synced_at.desc().nullslast(), Player.updated_at.desc())
        .first()
    )
    if not sheet_player:
        return player_read

    fallback = player_read.model_copy(
        update={
            "sheet_adp": player_read.sheet_adp if player_read.sheet_adp is not None else sheet_player.sheet_adp,
            "sheet_projected_season_points": (
                player_read.sheet_projected_season_points
                if player_read.sheet_projected_season_points is not None
                else sheet_player.sheet_projected_season_points
            ),
            "sheet_projection_stats": player_read.sheet_projection_stats or sheet_player.sheet_projection_stats,
            "sheet_source_sheet_id": player_read.sheet_source_sheet_id or sheet_player.sheet_source_sheet_id,
            "sheet_synced_at": player_read.sheet_synced_at or sheet_player.sheet_synced_at,
        }
    )
    return fallback


@router.post("", response_model=list[PlayerRead], status_code=status.HTTP_201_CREATED)
def create_players_endpoint(
    players_in: list[PlayerCreate],
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin_user),
) -> list[PlayerRead]:
    return create_players(db, players_in)


@router.get("", response_model=PlayerList)
def list_players_endpoint(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    position: str | None = None,
    school: str | None = None,
    search: str | None = None,
    league_id: int | None = None,
    available_only: bool = False,
    draft_eligible: bool = False,
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
        draft_eligible=draft_eligible,
        sort=sort,
    )
    return PlayerList(data=players, total=total, limit=limit, offset=offset)


@router.get("/{player_id}", response_model=PlayerRead)
def get_player_endpoint(player_id: int, db: Session = Depends(get_db)) -> PlayerRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    if is_retired_canonical_preseason_player(player, 2026):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="player is inactive for the current season")
    return player


@router.get("/{player_id}/card", response_model=PlayerCardRead)
def get_player_card_endpoint(
    player_id: int,
    request: Request,
    refresh: bool = False,
    injury_season: int | None = Query(default=None, ge=2020, le=2100),
    injury_week: int = Query(default=1, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> PlayerCardRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    if is_retired_canonical_preseason_player(player, 2026):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="player is inactive for the current season")

    if refresh and (current_user is None or not current_user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    if refresh:
        enforce_auth_rate_limit(
            db,
            action="provider_refresh",
            identifier=str(current_user.id),
            request=request,
            limit=settings.provider_refresh_rate_limit,
        )

    profile_payload: dict | None = None
    profile_message: str | None = None
    espn_client = ESPNClient()
    espn_id = resolve_espn_player_id(db, player)
    if refresh and not espn_id and settings.espn_historical_stats_enabled:
        try:
            resolved = resolve_espn_player_by_name(db, player, client=espn_client)
            if resolved:
                espn_id = resolved.provider_player_id
                profile_payload = resolved.profile_payload
        except Exception as exc:
            profile_message = f"ESPN profile lookup unavailable: {exc}"

    if refresh and espn_id:
        if profile_payload is None:
            try:
                profile_payload = espn_client.get_athlete_profile(espn_id)
                persist_espn_player_profile(player, profile_payload)
                db.commit()
            except Exception as exc:
                profile_message = f"ESPN profile unavailable: {exc}"
    else:
        profile_message = None

    current_injury_season = injury_season or datetime.now(timezone.utc).year
    current_injury_row = (
        db.query(Injury)
        .filter(
            Injury.player_id == player.id,
            Injury.season == current_injury_season,
            Injury.week == injury_week,
        )
        .order_by(Injury.updated_at.desc(), Injury.id.desc())
        .first()
    )
    current_injury_status = (
        normalize_injury_status(current_injury_row.status)
        if current_injury_row and is_current_injury_designation(current_injury_row.status)
        else None
    )
    injury_rows = (
        db.query(Injury)
        .filter(Injury.player_id == player.id)
        .order_by(Injury.season.desc(), Injury.week.desc(), Injury.updated_at.desc())
        .all()
    )
    news_rows = (
        db.query(PlayerNewsEvent)
        .filter(PlayerNewsEvent.player_id == player.id)
        .order_by(PlayerNewsEvent.published_at.desc(), PlayerNewsEvent.id.desc())
        .limit(25)
        .all()
    )
    stat_rows = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player.id)
        .order_by(PlayerStat.season.desc(), PlayerStat.week.desc(), PlayerStat.updated_at.desc())
        .all()
    )
    historical_stats = get_player_historical_stats_response(db, player)
    should_import_history = (
        settings.espn_historical_stats_enabled
        and espn_id is not None
        and refresh
    )
    if should_import_history:
        try:
            historical_stats = fetch_and_store_player_history(db, player)
        except Exception as exc:
            db.rollback()
            if not settings.espn_historical_stats_fail_open:
                raise
            historical_stats.message = f"{historical_stats.message or 'ESPN historical stats unavailable.'} {exc}"

    card_player = _player_card_player_with_sheet_projection_fallback(db, player)
    # Card reads are intentionally retrieval-only. The explicit batch job is
    # the sole generator so an opened card never creates unreviewed copy.
    season_outlook = get_persisted_player_season_outlook(
        db,
        player_id=player.id,
        season_year=datetime.now(timezone.utc).year,
    )
    return PlayerCardRead(
        player=card_player,
        about=_map_espn_about(player, card_player, profile_payload, profile_message, espn_player_id=espn_id),
        current_injury_status=current_injury_status,
        injuries=[
            PlayerCardInjuryRead(
                id=row.id,
                season=row.season,
                week=row.week,
                status=row.status,
                injury=row.injury,
                return_timeline=row.return_timeline,
                practice_level=row.practice_level,
                is_game_time_decision=row.is_game_time_decision,
                is_returning=row.is_returning,
                notes=row.notes,
                updated_at=row.updated_at,
            )
            for row in injury_rows
        ],
        recent_news=[
            PlayerCardNewsRead(
                id=row.id,
                event_type=row.event_type,
                status=(
                    next(
                        (
                            injury.status
                            for injury in injury_rows
                            if injury.season == row.season and injury.week == row.week
                        ),
                        None,
                    )
                ),
                detail=row.notes,
                source=row.source,
                source_url=row.source_url,
                published_at=_as_utc_timestamp(row.published_at),
                return_timeline=(
                    next(
                        (
                            injury.return_timeline
                            for injury in injury_rows
                            if injury.season == row.season and injury.week == row.week
                        ),
                        None,
                    )
                ),
            )
            for row in news_rows
        ],
        season_stats=[
            PlayerCardStatRowRead(
                season=row.season,
                week=row.week,
                source=row.source,
                stats=row.stats,
                updated_at=row.updated_at,
            )
            for row in stat_rows
        ],
        season_outlook=(
            PlayerSeasonOutlookRead.model_validate(season_outlook)
            if season_outlook is not None
            else None
        ),
        historical_stats=historical_stats,
    )


@router.get("/{player_id}/game-log", response_model=PlayerGameLogRead)
def get_player_game_log_endpoint(
    player_id: int,
    season: int | None = Query(default=None, ge=2000, le=2100),
    league_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> PlayerGameLogRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    try:
        return build_player_game_log(db, player, season=season, league_id=league_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{player_id}/historical-stats", response_model=PlayerHistoricalStatsResponse)
def get_player_historical_stats_endpoint(
    player_id: int,
    season: int | None = None,
    league_id: int | None = None,
    db: Session = Depends(get_db),
) -> PlayerHistoricalStatsResponse:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return get_player_historical_stats_response(db, player, season=season, league_id=league_id)


@router.get("/{player_id}/season-stats", response_model=PlayerStatResponse)
def get_player_season_stats_endpoint(
    player_id: int,
    request: Request,
    season: int = 2025,
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> PlayerStatResponse:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    week_value = 0
    existing = get_player_stat(db, player_id, season, week_value)
    stale = _is_stale(existing.updated_at, settings.sportsdata_cache_ttl_days) if existing else True
    if refresh and (current_user is None or not current_user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    if refresh:
        enforce_auth_rate_limit(
            db,
            action="provider_refresh",
            identifier=str(current_user.id),
            request=request,
            limit=settings.provider_refresh_rate_limit,
        )
    should_refresh = refresh

    if existing and not should_refresh:
        return PlayerStatResponse(
            player_id=player_id,
            season=season,
            week=week_value,
            source=existing.source,
            cached=True,
            stats=existing.stats,
        )

    if not settings.sportsdata_api_key and not existing:
        return PlayerStatResponse(
            player_id=player_id,
            season=season,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="SPORTSDATA_API_KEY is not configured.",
        )

    if not player.external_id and not existing:
        return PlayerStatResponse(
            player_id=player_id,
            season=season,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="Player external_id is not set for SportsData lookup.",
        )

    def _refresh_from_provider() -> None:
        if not settings.sportsdata_api_key:
            raise RuntimeError("SPORTSDATA_API_KEY is not configured.")
        if not player.external_id:
            raise RuntimeError("Player external_id is not set for SportsData lookup.")
        client = SportsDataClient()
        stats = client.get_player_stats(player.external_id)
        if not stats:
            raise RuntimeError("No season stats returned from SportsData.")
        upsert_player_stat(db, player_id, season, week_value, stats=stats, source="sportsdata")

    refreshed = False
    stale_fallback_message: str | None = None
    if should_refresh:
        try:
            refreshed, _state = ensure_feed_fresh(
                db,
                provider="sportsdata",
                feed="player_season_stats",
                scope={
                    "player_id": player.id,
                    "external_id": player.external_id,
                    "season": season,
                    "week": week_value,
                },
                refresh_fn=_refresh_from_provider,
                ttl_days=settings.sportsdata_cache_ttl_days,
                force_refresh=refresh or stale or not existing,
            )
            db.commit()
        except Exception as exc:
            if not existing:
                return PlayerStatResponse(
                    player_id=player_id,
                    season=season,
                    week=week_value,
                    source="sportsdata",
                    cached=False,
                    stats=None,
                    message=str(exc),
                )
            stale_fallback_message = f"Using stale cached season stats: {exc}"

    stored = get_player_stat(db, player_id, season, week_value) or existing
    if not stored:
        return PlayerStatResponse(
            player_id=player_id,
            season=season,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="No season stats available.",
        )

    return PlayerStatResponse(
        player_id=player_id,
        season=season,
        week=week_value,
        source=stored.source,
        cached=not refreshed,
        stats=stored.stats,
        message=stale_fallback_message,
    )


@router.get("/{player_id}/stats", response_model=PlayerStatResponse)
def get_player_stats_endpoint(
    player_id: int,
    request: Request,
    season: int | None = None,
    week: int | None = None,
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> PlayerStatResponse:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    season_value = season or datetime.now().year
    week_value = week or 1

    existing = get_player_stat(db, player_id, season_value, week_value)
    stale = _is_stale(existing.updated_at, settings.sportsdata_cache_ttl_days) if existing else True
    if refresh and (current_user is None or not current_user.is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    if refresh:
        enforce_auth_rate_limit(
            db,
            action="provider_refresh",
            identifier=str(current_user.id),
            request=request,
            limit=settings.provider_refresh_rate_limit,
        )
    should_refresh = refresh

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
