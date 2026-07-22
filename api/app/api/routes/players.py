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
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.player import (
    PlayerCardAboutRead,
    PlayerCardInjuryRead,
    PlayerCardRead,
    PlayerCardStatRowRead,
    PlayerCreate,
    PlayerList,
    PlayerRead,
)
from collegefootballfantasy_api.app.schemas.historical_stats import PlayerHistoricalStatsResponse
from collegefootballfantasy_api.app.schemas.game_log import PlayerGameLogRead
from collegefootballfantasy_api.app.schemas.player_stat import PlayerStatResponse
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
from collegefootballfantasy_api.app.services.provider_cache import ensure_feed_fresh
from collegefootballfantasy_api.app.services.auth_security import enforce_auth_rate_limit

router = APIRouter()


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
            height=stored_player.espn_height,
            weight=stored_player.espn_weight,
            player_class=player.player_class,
            birthplace=stored_player.espn_birthplace,
            status=stored_player.espn_status or "Active",
            jersey=stored_player.espn_jersey,
            position=player.position,
            team=player.school,
            headshot_url=stored_player.espn_headshot_url or player.image_url,
            source="espn" if stored_player.espn_profile_synced_at else "local",
            message=message,
        )
    status = athlete.get("status") if isinstance(athlete.get("status"), dict) else {}
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    headshot = athlete.get("headshot") if isinstance(athlete.get("headshot"), dict) else {}
    return PlayerCardAboutRead(
        espn_player_id=_profile_text(athlete.get("id")) or espn_player_id or _espn_player_id(player.external_id),
        height=_profile_text(athlete.get("displayHeight")) or stored_player.espn_height,
        weight=_profile_text(athlete.get("displayWeight")) or stored_player.espn_weight,
        player_class=player.player_class,
        birthplace=_birthplace(athlete) or stored_player.espn_birthplace,
        status=_profile_text(status.get("name") or status.get("abbreviation")) or stored_player.espn_status or "Active",
        jersey=_profile_text(athlete.get("jersey")) or stored_player.espn_jersey,
        position=_profile_text(position.get("displayName") or position.get("abbreviation")) or player.position,
        team=_profile_text(team.get("displayName") or team.get("shortDisplayName")) or player.school,
        headshot_url=_profile_text(headshot.get("href")) or stored_player.espn_headshot_url or player.image_url,
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


@router.get("/{player_id}/card", response_model=PlayerCardRead)
def get_player_card_endpoint(
    player_id: int,
    request: Request,
    refresh: bool = False,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> PlayerCardRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

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

    injury_rows = (
        db.query(Injury)
        .filter(Injury.player_id == player.id)
        .order_by(Injury.season.desc(), Injury.week.desc(), Injury.updated_at.desc())
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
    return PlayerCardRead(
        player=card_player,
        about=_map_espn_about(player, card_player, profile_payload, profile_message, espn_player_id=espn_id),
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
        historical_stats=historical_stats,
    )


@router.get("/{player_id}/game-log", response_model=PlayerGameLogRead)
def get_player_game_log_endpoint(
    player_id: int,
    season: int = Query(2026, ge=2000, le=2100),
    db: Session = Depends(get_db),
) -> PlayerGameLogRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return build_player_game_log(db, player, season=season)


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
