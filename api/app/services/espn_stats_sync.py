from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import ESPNClient, extract_player_box_score_stats
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.provider_identity import record_unmatched_provider_row


class UnresolvedKickerDistanceError(ValueError):
    """A made ESPN field goal cannot be assigned to a safe scoring tier."""


def _identity(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _school_keys(row: dict[str, Any]) -> set[str]:
    keys = {_identity(str(row.get("School") or "")), _identity(str(row.get("Team") or ""))}
    aliases = row.get("TeamAliases")
    if isinstance(aliases, list):
        keys.update(_identity(str(alias)) for alias in aliases)
    return {key for key in keys if key}


def _build_player_indexes(players: list[Player]) -> tuple[dict[str, Player], dict[tuple[str, str], list[Player]]]:
    external_index: dict[str, Player] = {}
    name_school_index: dict[tuple[str, str], list[Player]] = {}
    for player in players:
        if player.external_id:
            external_id = str(player.external_id)
            external_index[external_id] = player
            external_index[external_id.removeprefix("espn:")] = player
        name_key = _identity(player.name)
        school_key = _identity(player.school)
        if name_key and school_key:
            name_school_index.setdefault((name_key, school_key), []).append(player)
    return external_index, name_school_index


def _build_provider_player_index(db: Session) -> dict[str, Player]:
    mappings = (
        db.query(PlayerProviderId)
        .filter(PlayerProviderId.provider == "espn")
        # Live authority must be an explicitly reviewed mapping. Historical
        # tools retain their isolated fallback behavior, but they may never
        # promote an inherited/legacy mapping into live fantasy scoring.
        .filter(PlayerProviderId.verification_status == "verified")
        .all()
    )
    return {mapping.provider_player_id: mapping.player for mapping in mappings}


def _match_player(
    row: dict[str, Any],
    provider_index: dict[str, Player],
    external_index: dict[str, Player],
    name_school_index: dict[tuple[str, str], list[Player]],
    *,
    strict_identity: bool,
) -> tuple[Player | None, str | None]:
    espn_player_id = str(row.get("ESPNPlayerID") or "")
    if espn_player_id:
        player = provider_index.get(espn_player_id)
        if player:
            return player, None

    # Shadow and public live scoring require a reviewed ESPN player identity.
    # External-ID and name/school fallbacks are retained only for isolated
    # historical import tooling, never for authoritative fantasy updates.
    if strict_identity:
        return None, "missing verified ESPN player identity"

    for external_id in (espn_player_id, f"espn:{espn_player_id}"):
        player = external_index.get(external_id)
        if player:
            return player, None

    name_key = _identity(str(row.get("PlayerName") or ""))
    if not name_key:
        return None, "missing player name"
    for school_key in _school_keys(row):
        matches = name_school_index.get((name_key, school_key), [])
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "ambiguous name-school match"
    return None, "no provider identity mapping or unique name-school fallback"


def normalize_espn_summary_player_stats(
    db: Session,
    *,
    season: int,
    week: int,
    summary: dict[str, Any],
    strict_identity: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Normalize one ESPN game summary without writing public fantasy stats.

    Each returned row includes the verified internal player ID.  In strict
    mode the only admissible path is ESPNPlayerID -> verified
    PlayerProviderId(provider="espn").  This keeps historical importer
    heuristics isolated from live/shadow authority.
    """

    raw_rows = extract_player_box_score_stats(summary)
    players = db.query(Player).all()
    provider_index = _build_provider_player_index(db)
    external_index, name_school_index = _build_player_indexes(players)
    normalized: list[dict[str, Any]] = []
    skipped = 0
    for row in raw_rows:
        player, unmatched_reason = _match_player(
            row,
            provider_index,
            external_index,
            name_school_index,
            strict_identity=strict_identity,
        )
        if player is None:
            record_unmatched_provider_row(
                db,
                provider="espn",
                feed="live_boxscore_player_stats" if strict_identity else "weekly_boxscore_player_stats",
                row=row,
                season=season,
                week=week,
                reason=unmatched_reason,
            )
            skipped += 1
            continue
        if strict_identity and player.position in {"K", "PK"} and row.get("espn_field_goal_distance_detail_available") is False:
            reason = str(row.get("espn_field_goal_distance_detail_reason") or "made_field_goal_distance_unavailable")
            record_unmatched_provider_row(
                db,
                provider="espn",
                feed="live_boxscore_kicker_distance",
                row=row,
                season=season,
                week=week,
                reason=reason,
            )
            db.flush()
            raise UnresolvedKickerDistanceError(
                f"verified kicker {player.id} has a made field goal without an exact ESPN distance"
            )
        normalized.append({"player_id": player.id, "stats": row})
    return normalized, skipped


def persist_normalized_espn_player_stats(
    db: Session,
    *,
    season: int,
    week: int,
    normalized_rows: list[dict[str, Any]],
) -> int:
    """Promote already-verified cumulative ESPN totals to PlayerStat rows."""

    upserted = 0
    for normalized in normalized_rows:
        player_id = int(normalized["player_id"])
        stats = dict(normalized["stats"])
        stat = (
            db.query(PlayerStat)
            .filter(
                PlayerStat.player_id == player_id,
                PlayerStat.season == season,
                PlayerStat.week == week,
            )
            .first()
        )
        if stat is None:
            stat = PlayerStat(player_id=player_id, season=season, week=week, source="espn", stats=stats)
            db.add(stat)
        else:
            # ESPN box-score rows are cumulative current-game totals.  Replace
            # the prior verified total; never add snapshots together.
            stat.source = "espn"
            stat.stats = stats
        upserted += 1
    return upserted


def persist_final_espn_player_game_stats(
    db: Session,
    *,
    season: int,
    week: int,
    game_id: int,
    normalized_rows: list[dict[str, Any]],
) -> int:
    """Persist one accepted final ESPN box score per player/game.

    ``PlayerStat`` remains the current-week scoring authority. This separate
    game-keyed record is written only after the provider marks the game final,
    so player-card game logs and season totals never treat a live snapshot as
    a completed performance.
    """

    upserted = 0
    for normalized in normalized_rows:
        player_id = int(normalized["player_id"])
        stats = dict(normalized["stats"])
        stat = (
            db.query(PlayerGameStat)
            .filter(PlayerGameStat.player_id == player_id, PlayerGameStat.game_id == game_id)
            .one_or_none()
        )
        if stat is None:
            stat = PlayerGameStat(
                player_id=player_id,
                game_id=game_id,
                season=season,
                week=week,
                source="espn_final_boxscore",
                stats=stats,
            )
            db.add(stat)
        else:
            # A verified ESPN final correction replaces this game's prior
            # total; it is never added to the existing box score.
            if (
                stat.season == season
                and stat.week == week
                and stat.source == "espn_final_boxscore"
                and stat.stats == stats
            ):
                continue
            stat.season = season
            stat.week = week
            stat.source = "espn_final_boxscore"
            stat.stats = stats
        upserted += 1
    return upserted


def upsert_espn_weekly_player_stats(
    db: Session,
    *,
    season: int,
    week: int,
    client: ESPNClient | None = None,
) -> dict[str, int]:
    created_client = client is None
    espn = client or ESPNClient()
    try:
        summaries = espn.get_weekly_boxscore_summaries(season=season, week=week)
        rows = [row for summary in summaries for row in extract_player_box_score_stats(summary)]
        normalized_rows: list[dict[str, Any]] = []
        skipped = 0
        for summary in summaries:
            normalized, summary_skipped = normalize_espn_summary_player_stats(
                db,
                season=season,
                week=week,
                summary=summary,
                strict_identity=False,
            )
            normalized_rows.extend(normalized)
            skipped += summary_skipped
        upserted = persist_normalized_espn_player_stats(
            db,
            season=season,
            week=week,
            normalized_rows=normalized_rows,
        )

        db.commit()
        return {
            "events": len(summaries),
            "rows_seen": len(rows),
            "upserted": upserted,
            "skipped": skipped,
            "unmatched_rows": skipped,
            "unmatched_rate": round(skipped / len(rows), 4) if rows else 0,
        }
    finally:
        if created_client:
            espn.close()
