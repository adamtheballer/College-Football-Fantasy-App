from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user, get_league_or_404, require_league_member
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.crud.player import create_players, get_player, list_players
from collegefootballfantasy_api.app.crud.player_stat import get_player_stat, upsert_player_stat
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.schemas.player import (
    PlayerCardAboutRead,
    PlayerCardInjuryRead,
    PlayerCardRead,
    PlayerCardStatRowRead,
    PlayerCreate,
    PlayerList,
    PlayerPoolList,
    PlayerProfileRead,
    PlayerRead,
)
from collegefootballfantasy_api.app.schemas.player_stat import PlayerStatResponse
from collegefootballfantasy_api.app.services.player_profile import build_player_profile
from collegefootballfantasy_api.app.services.player_search import list_player_pool
from collegefootballfantasy_api.app.services.provider_cache import ensure_feed_fresh
from collegefootballfantasy_api.app.services.provider_identity_audit import provider_id_for_player

router = APIRouter()


def _espn_player_id(external_id: str | None) -> str | None:
    if not external_id:
        return None
    normalized = str(external_id).strip()
    if not normalized:
        return None
    if normalized.lower().startswith("espn:"):
        normalized = normalized.split(":", 1)[1].strip()
    return normalized or None


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
    player: PlayerRead,
    payload: dict | None,
    message: str | None = None,
    espn_player_id: str | None = None,
) -> PlayerCardAboutRead:
    athlete = payload.get("athlete") if isinstance(payload, dict) else None
    if not isinstance(athlete, dict):
        return PlayerCardAboutRead(
            espn_player_id=espn_player_id or _espn_player_id(player.external_id),
            player_class=player.player_class,
            position=player.position,
            team=player.school,
            source="local",
            message=message,
        )
    status = athlete.get("status") if isinstance(athlete.get("status"), dict) else {}
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    headshot = athlete.get("headshot") if isinstance(athlete.get("headshot"), dict) else {}
    return PlayerCardAboutRead(
        espn_player_id=_profile_text(athlete.get("id")) or espn_player_id or _espn_player_id(player.external_id),
        height=_profile_text(athlete.get("displayHeight")),
        weight=_profile_text(athlete.get("displayWeight")),
        player_class=player.player_class,
        birthplace=_birthplace(athlete),
        status=_profile_text(status.get("name") or status.get("abbreviation")) or "Active",
        jersey=_profile_text(athlete.get("jersey")),
        position=_profile_text(position.get("displayName") or position.get("abbreviation")) or player.position,
        team=_profile_text(team.get("displayName") or team.get("shortDisplayName")) or player.school,
        headshot_url=_profile_text(headshot.get("href")) or player.image_url,
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


def _optional_user_from_header(db: Session, authorization: str | None):
    if not authorization:
        return None
    return get_current_user(db, authorization)


def _sportsdata_player_id(player) -> str | None:
    return provider_id_for_player(player, "sportsdata")


@router.post("", response_model=list[PlayerRead], status_code=status.HTTP_201_CREATED)
def create_players_endpoint(
    players_in: list[PlayerCreate], db: Session = Depends(get_db)
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


@router.get("/pool", response_model=PlayerPoolList)
def list_player_pool_endpoint(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    position: str | None = None,
    team: str | None = None,
    conference: str | None = None,
    league_id: int | None = None,
    season: int | None = None,
    week: int | None = None,
    availability: str | None = None,
    injury_status: str | None = None,
    sort: str | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> PlayerPoolList:
    current_user = _optional_user_from_header(db, authorization)
    league = None
    if league_id is not None:
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")
        league = get_league_or_404(db, league_id)
        require_league_member(db, league.id, current_user)
    return list_player_pool(
        db,
        current_user=current_user,
        league=league,
        season=season,
        week=week,
        limit=limit,
        offset=offset,
        search=search,
        position=position,
        team=team,
        conference=conference,
        availability=availability,
        injury_status=injury_status,
        sort=sort,
    )


@router.get("/{player_id}", response_model=PlayerRead)
def get_player_endpoint(player_id: int, db: Session = Depends(get_db)) -> PlayerRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return player


@router.get("/{player_id}/profile", response_model=PlayerProfileRead)
def get_player_profile_endpoint(
    player_id: int,
    league_id: int | None = None,
    season: int | None = None,
    week: int | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> PlayerProfileRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    current_user = _optional_user_from_header(db, authorization)
    league = None
    if league_id is not None:
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")
        league = get_league_or_404(db, league_id)
        require_league_member(db, league.id, current_user)
    target_season = season or (league.season_year if league else 2026)
    return build_player_profile(
        db,
        player=player,
        current_user=current_user,
        league=league,
        season=target_season,
        week=week,
    )


@router.get("/{player_id}/card", response_model=PlayerCardRead)
def get_player_card_endpoint(
    player_id: int,
    refresh: bool = False,
    db: Session = Depends(get_db),
) -> PlayerCardRead:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    profile_payload: dict | None = None
    profile_message: str | None = None
    espn_id = provider_id_for_player(player, "espn")
    if espn_id:
        try:
            profile_payload = ESPNClient().get_athlete_profile(espn_id)
        except Exception as exc:
            profile_message = f"ESPN profile unavailable: {exc}"
    else:
        profile_message = "No ESPN player ID is set for this player."

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
    return PlayerCardRead(
        player=player,
        about=_map_espn_about(player, profile_payload, profile_message, espn_player_id=espn_id),
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
    )


@router.get("/{player_id}/season-stats", response_model=PlayerStatResponse)
def get_player_season_stats_endpoint(
    player_id: int,
    season: int = 2025,
    refresh: bool = False,
    db: Session = Depends(get_db),
) -> PlayerStatResponse:
    player = get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")

    week_value = 0
    existing = get_player_stat(db, player_id, season, week_value)
    stale = _is_stale(existing.updated_at, settings.sportsdata_cache_ttl_days) if existing else True
    should_refresh = refresh or not existing or stale

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

    sportsdata_player_id = _sportsdata_player_id(player)

    if not sportsdata_player_id and not existing:
        return PlayerStatResponse(
            player_id=player_id,
            season=season,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="Player SportsData provider ID is not set.",
        )

    def _refresh_from_provider() -> None:
        if not settings.sportsdata_api_key:
            raise RuntimeError("SPORTSDATA_API_KEY is not configured.")
        if not sportsdata_player_id:
            raise RuntimeError("Player SportsData provider ID is not set.")
        client = SportsDataClient()
        stats = client.get_player_stats(sportsdata_player_id)
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
                    "provider_player_id": sportsdata_player_id,
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

    sportsdata_player_id = _sportsdata_player_id(player)

    if not sportsdata_player_id and not existing:
        return PlayerStatResponse(
            player_id=player_id,
            season=season_value,
            week=week_value,
            source="sportsdata",
            cached=False,
            stats=None,
            message="Player SportsData provider ID is not set.",
        )

    def _refresh_from_provider() -> None:
        if not sportsdata_player_id:
            raise RuntimeError("Player SportsData provider ID is not set.")
        client = SportsDataClient()
        stats = client.get_player_stats(sportsdata_player_id, season=season_value, week=week_value)
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
                    "provider_player_id": sportsdata_player_id,
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
