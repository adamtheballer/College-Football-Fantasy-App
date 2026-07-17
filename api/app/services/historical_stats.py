from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.college_team import CollegeTeam
from collegefootballfantasy_api.app.models.historical_stats import (
    PlayerHistoricalSeasonStat,
    ProviderStatCache,
)
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId, TeamProviderId
from collegefootballfantasy_api.app.schemas.historical_stats import (
    HistoricalStatsCategory,
    HistoricalStatsFreshness,
    HistoricalStatsScoringContext,
    HistoricalStatValue,
    PlayerHistoricalSeasonRead,
    PlayerHistoricalStatsResponse,
)
from collegefootballfantasy_api.app.services.providers.espn_historical.parser import parse_player_history
from collegefootballfantasy_api.app.services.providers.espn_historical.provider import ESPNHistoricalPlayerStatsProvider
from collegefootballfantasy_api.app.services.providers.espn_historical.schemas import (
    PARSER_VERSION,
    SCHEMA_VERSION,
    ProviderPlayerHistory,
    ProviderPlayerSeason,
)
from collegefootballfantasy_api.app.services.scoring_service import calculate_player_fantasy_points, normalize_player_stats


TRUSTED_PROVIDER_MAPPING_STATUSES = {"verified", "manual", "legacy_backfill", "auto_matched"}


def canonical_json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def legacy_espn_player_id(external_id: str | None) -> str | None:
    if not external_id:
        return None
    text = str(external_id).strip()
    if not text:
        return None
    if text.lower().startswith("espn:"):
        return text.split(":", 1)[1].strip() or None
    return text if text.isdecimal() else None


def resolve_espn_player_id(db: Session, player: Player) -> str | None:
    mapping = (
        db.query(PlayerProviderId)
        .filter(PlayerProviderId.player_id == player.id, PlayerProviderId.provider == "espn")
        .order_by(PlayerProviderId.verified_at.desc().nullslast(), PlayerProviderId.updated_at.desc())
        .first()
    )
    if mapping and mapping.provider_player_id:
        status = (mapping.verification_status or "").lower()
        confidence = mapping.match_confidence if mapping.match_confidence is not None else 0.0
        if status in TRUSTED_PROVIDER_MAPPING_STATUSES or confidence >= 0.9:
            return str(mapping.provider_player_id).strip() or None
    return legacy_espn_player_id(player.external_id)


def _team_id_for_provider_team(db: Session, provider_team_id: str | None, team_name: str | None) -> int | None:
    if provider_team_id:
        mapping = (
            db.query(TeamProviderId)
            .filter(TeamProviderId.provider == "espn", TeamProviderId.provider_team_id == str(provider_team_id))
            .first()
        )
        if mapping:
            return mapping.team_id
    if team_name:
        team = db.query(CollegeTeam).filter(CollegeTeam.name == team_name).first()
        return team.id if team else None
    return None


def _flatten_season_categories(season: ProviderPlayerSeason) -> dict[str, float | None]:
    flattened: dict[str, float | None] = {}
    for category_stats in season.categories.values():
        flattened.update(category_stats)
    return flattened


def _scoring_stats_from_historical_row(row: PlayerHistoricalSeasonStat) -> dict[str, float | None]:
    field_goals_0_39 = sum(
        value or 0
        for value in (row.field_goals_0_19, row.field_goals_20_29, row.field_goals_30_39)
    )
    return {
        "pass_yards": row.passing_yards,
        "pass_tds": row.passing_touchdowns,
        "interceptions": row.interceptions,
        "rush_yards": row.rushing_yards,
        "rush_tds": row.rushing_touchdowns,
        "receptions": row.receptions,
        "rec_yards": row.receiving_yards,
        "rec_tds": row.receiving_touchdowns,
        "fumbles_lost": row.fumbles_lost,
        "fg_made_0_39": field_goals_0_39,
        "fg_made_40_49": row.field_goals_40_49,
        "fg_made_50_plus": row.field_goals_50_plus,
        "xp_made": row.extra_points_made,
    }


def _league_scoring_rules(db: Session, league_id: int | None) -> tuple[dict[str, Any], str]:
    if not league_id:
        return {}, "default"
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not settings_row:
        return {}, "default"
    return settings_row.scoring_json or {}, f"league:{league_id}"


def _assign_stats(row: PlayerHistoricalSeasonStat, flattened: dict[str, float | None]) -> None:
    fields = [
        "passing_completions",
        "passing_attempts",
        "passing_yards",
        "passing_touchdowns",
        "interceptions",
        "sacks_taken",
        "rushing_attempts",
        "rushing_yards",
        "rushing_touchdowns",
        "long_rush",
        "receptions",
        "receiving_targets",
        "receiving_yards",
        "receiving_touchdowns",
        "long_reception",
        "kick_return_attempts",
        "kick_return_yards",
        "kick_return_touchdowns",
        "punt_return_attempts",
        "punt_return_yards",
        "punt_return_touchdowns",
        "field_goals_made",
        "field_goals_attempted",
        "field_goals_0_19",
        "field_goals_20_29",
        "field_goals_30_39",
        "field_goals_40_49",
        "field_goals_50_plus",
        "extra_points_made",
        "extra_points_attempted",
        "fumbles",
        "fumbles_lost",
    ]
    for field in fields:
        setattr(row, field, flattened.get(field))


def upsert_historical_player_history(
    db: Session,
    player: Player,
    history: ProviderPlayerHistory,
    *,
    source_response_hash: str | None = None,
    league_id: int | None = None,
    refresh_finalized: bool = False,
) -> tuple[int, int]:
    scoring_rules, scoring_rules_version = _league_scoring_rules(db, league_id)
    rows_inserted = 0
    rows_updated = 0
    imported_at = datetime.now(timezone.utc)
    for season in history.seasons:
        row = (
            db.query(PlayerHistoricalSeasonStat)
            .filter(
                PlayerHistoricalSeasonStat.player_id == player.id,
                PlayerHistoricalSeasonStat.provider == history.provider,
                PlayerHistoricalSeasonStat.season == season.season,
                PlayerHistoricalSeasonStat.season_type == season.season_type,
            )
            .first()
        )
        if row and row.is_final and not refresh_finalized:
            continue
        if not row:
            row = PlayerHistoricalSeasonStat(
                player_id=player.id,
                provider=history.provider,
                provider_player_id=history.provider_player_id,
                season=season.season,
                season_type=season.season_type,
                parser_version=PARSER_VERSION,
                imported_at=imported_at,
            )
            db.add(row)
            rows_inserted += 1
        else:
            rows_updated += 1

        flattened = _flatten_season_categories(season)
        row.provider_player_id = history.provider_player_id
        row.provider_team_id = season.team_provider_id
        row.team_name = season.team_name
        row.team_id = _team_id_for_provider_team(db, season.team_provider_id, season.team_name)
        row.position = season.position
        row.games_played = season.games_played
        row.games_started = season.games_started
        _assign_stats(row, flattened)
        normalized_stats = normalize_player_stats(_scoring_stats_from_historical_row(row))
        fantasy_points, _breakdown = calculate_player_fantasy_points(normalized_stats, scoring_rules)
        row.fantasy_points = fantasy_points
        row.fantasy_points_per_game = (
            round(fantasy_points / row.games_played, 2) if row.games_played and row.games_played > 0 else None
        )
        row.scoring_rules_version = scoring_rules_version
        row.source_response_hash = source_response_hash
        row.parser_version = PARSER_VERSION
        row.imported_at = imported_at
        row.provider_updated_at = season.provider_updated_at
        row.raw_labels = season.raw_labels
        row.unknown_labels = season.unknown_labels
    db.flush()
    return rows_inserted, rows_updated


def cache_provider_response(
    db: Session,
    *,
    provider_player_id: str,
    response_json: dict[str, Any],
    http_status: int | None = 200,
    is_valid: bool = True,
    validation_error: str | None = None,
) -> ProviderStatCache:
    now = datetime.now(timezone.utc)
    response_hash = canonical_json_hash(response_json)
    existing = (
        db.query(ProviderStatCache)
        .filter(
            ProviderStatCache.provider == "espn",
            ProviderStatCache.provider_player_id == provider_player_id,
            ProviderStatCache.request_kind == "athlete_stats",
            ProviderStatCache.season_start == 0,
            ProviderStatCache.season_end == 0,
            ProviderStatCache.response_hash == response_hash,
        )
        .order_by(ProviderStatCache.fetched_at.desc())
        .first()
    )
    if existing:
        existing.expires_at = now + timedelta(days=max(1, settings.espn_historical_stats_cache_ttl_days))
        return existing
    cache_row = ProviderStatCache(
        provider="espn",
        provider_player_id=provider_player_id,
        request_kind="athlete_stats",
        season_start=0,
        season_end=0,
        response_json=response_json,
        response_hash=response_hash,
        http_status=http_status,
        fetched_at=now,
        parser_version=PARSER_VERSION,
        schema_version=SCHEMA_VERSION,
        is_valid=is_valid,
        validation_error=validation_error,
        expires_at=now + timedelta(days=max(1, settings.espn_historical_stats_cache_ttl_days)),
    )
    db.add(cache_row)
    db.flush()
    return cache_row


def fetch_and_store_player_history(
    db: Session,
    player: Player,
    *,
    provider: ESPNHistoricalPlayerStatsProvider | None = None,
    league_id: int | None = None,
    allow_disabled: bool = False,
) -> PlayerHistoricalStatsResponse:
    if not settings.espn_historical_stats_enabled and not allow_disabled:
        return PlayerHistoricalStatsResponse(
            player_id=player.id,
            status="disabled",
            message="ESPN historical stats import is disabled.",
        )
    provider_player_id = resolve_espn_player_id(db, player)
    if not provider_player_id:
        return PlayerHistoricalStatsResponse(
            player_id=player.id,
            status="no_provider_mapping",
            message="No trusted ESPN provider mapping is linked to this player.",
        )
    stats_provider = provider or ESPNHistoricalPlayerStatsProvider()
    history = stats_provider.fetch_player_history(provider_player_id)
    response_hash = canonical_json_hash(history.raw_payload)
    cache_provider_response(db, provider_player_id=provider_player_id, response_json=history.raw_payload)
    upsert_historical_player_history(
        db,
        player,
        history,
        source_response_hash=response_hash,
        league_id=league_id,
    )
    return get_player_historical_stats_response(db, player, league_id=league_id)


def _value(label: str, value: float | int | str | None) -> HistoricalStatValue:
    return HistoricalStatValue(label=label, value=value)


def _category(label: str, key: str, pairs: list[tuple[str, float | int | str | None]]) -> HistoricalStatsCategory | None:
    stats = [_value(stat_label, stat_value) for stat_label, stat_value in pairs if stat_value is not None]
    if not stats:
        return None
    return HistoricalStatsCategory(key=key, label=label, stats=stats)


def _season_read(row: PlayerHistoricalSeasonStat) -> PlayerHistoricalSeasonRead:
    categories = [
        _category(
            "Passing",
            "passing",
            [
                ("Completions", row.passing_completions),
                ("Attempts", row.passing_attempts),
                ("Yards", row.passing_yards),
                ("TD", row.passing_touchdowns),
                ("INT", row.interceptions),
                ("Sacks", row.sacks_taken),
            ],
        ),
        _category(
            "Rushing",
            "rushing",
            [
                ("Attempts", row.rushing_attempts),
                ("Yards", row.rushing_yards),
                ("TD", row.rushing_touchdowns),
                ("Long", row.long_rush),
            ],
        ),
        _category(
            "Receiving",
            "receiving",
            [
                ("Receptions", row.receptions),
                ("Targets", row.receiving_targets),
                ("Yards", row.receiving_yards),
                ("TD", row.receiving_touchdowns),
                ("Long", row.long_reception),
            ],
        ),
        _category(
            "Kicking",
            "kicking",
            [
                ("FGM", row.field_goals_made),
                ("FGA", row.field_goals_attempted),
                ("FG 40-49", row.field_goals_40_49),
                ("FG 50+", row.field_goals_50_plus),
                ("XPM", row.extra_points_made),
            ],
        ),
        _category(
            "Returns",
            "returns",
            [
                ("KR", row.kick_return_attempts),
                ("KR Yds", row.kick_return_yards),
                ("KR TD", row.kick_return_touchdowns),
                ("PR", row.punt_return_attempts),
                ("PR Yds", row.punt_return_yards),
                ("PR TD", row.punt_return_touchdowns),
            ],
        ),
        _category(
            "Ball Security",
            "turnovers",
            [
                ("Fumbles", row.fumbles),
                ("Fumbles Lost", row.fumbles_lost),
            ],
        ),
    ]
    categories = [category for category in categories if category is not None]
    summary = [
        _value("Fantasy Pts", row.fantasy_points),
        _value("FPTS/G", row.fantasy_points_per_game),
        _value("Games", row.games_played),
        _value("Pass Yds", row.passing_yards),
        _value("Rush Yds", row.rushing_yards),
        _value("Rec Yds", row.receiving_yards),
        _value("TD", sum(value or 0 for value in (row.passing_touchdowns, row.rushing_touchdowns, row.receiving_touchdowns))),
    ]
    return PlayerHistoricalSeasonRead(
        season=row.season,
        season_type=row.season_type,
        team_name=row.team_name,
        position=row.position,
        games_played=row.games_played,
        games_started=row.games_started,
        summary=[item for item in summary if item.value is not None],
        categories=categories,
        freshness=HistoricalStatsFreshness(
            provider=row.provider,
            provider_player_id=row.provider_player_id,
            imported_at=row.imported_at,
            provider_updated_at=row.provider_updated_at,
            parser_version=row.parser_version,
            source_response_hash=row.source_response_hash,
            is_final=row.is_final,
        ),
        scoring_context=HistoricalStatsScoringContext(
            scoring_rules_version=row.scoring_rules_version,
            fantasy_points=row.fantasy_points,
            fantasy_points_per_game=row.fantasy_points_per_game,
        ),
        unknown_labels=row.unknown_labels,
    )


def get_player_historical_stats_response(
    db: Session,
    player: Player,
    *,
    season: int | None = None,
    league_id: int | None = None,
) -> PlayerHistoricalStatsResponse:
    if not settings.player_card_historical_stats_enabled:
        return PlayerHistoricalStatsResponse(
            player_id=player.id,
            status="disabled",
            message="Historical stats are disabled for player cards.",
        )

    provider_player_id = resolve_espn_player_id(db, player)
    if not provider_player_id:
        return PlayerHistoricalStatsResponse(
            player_id=player.id,
            status="no_provider_mapping",
            message="No trusted ESPN provider mapping is linked to this player.",
        )

    query = db.query(PlayerHistoricalSeasonStat).filter(
        PlayerHistoricalSeasonStat.player_id == player.id,
        PlayerHistoricalSeasonStat.provider == "espn",
    )
    if season:
        query = query.filter(PlayerHistoricalSeasonStat.season == season)
    rows = query.order_by(PlayerHistoricalSeasonStat.season.desc()).all()
    if not rows:
        return PlayerHistoricalStatsResponse(
            player_id=player.id,
            status="not_available",
            message="No imported ESPN historical stats are available for this player yet.",
            available_seasons=[],
            seasons=[],
        )
    seasons = [_season_read(row) for row in rows]
    return PlayerHistoricalStatsResponse(
        player_id=player.id,
        status="available",
        selected_season=seasons[0].season,
        available_seasons=[row.season for row in rows],
        seasons=seasons,
    )


def parse_and_store_cached_provider_response(
    db: Session,
    player: Player,
    payload: dict[str, Any],
    *,
    provider_player_id: str | None = None,
    league_id: int | None = None,
) -> tuple[int, int]:
    resolved_provider_player_id = provider_player_id or resolve_espn_player_id(db, player)
    if not resolved_provider_player_id:
        return 0, 0
    fetched_at = datetime.now(timezone.utc)
    history = parse_player_history(payload, provider_player_id=resolved_provider_player_id, fetched_at=fetched_at)
    response_hash = canonical_json_hash(payload)
    cache_provider_response(db, provider_player_id=resolved_provider_player_id, response_json=payload)
    return upsert_historical_player_history(
        db,
        player,
        history,
        source_response_hash=response_hash,
        league_id=league_id,
    )
