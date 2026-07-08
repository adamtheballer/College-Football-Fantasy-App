from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.provider_payload_validation import (
    ESPNPlayerStatPayload,
    ProviderPayloadValidationError,
)
from collegefootballfantasy_api.app.integrations.espn import ESPNClient, extract_player_box_score_stats
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.provider_identity_audit import (
    record_provider_identity_audit,
    record_unmatched_provider_row,
)
from collegefootballfantasy_api.app.services.provider_sync_jobs import run_provider_sync_job


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


def _match_player(
    row: dict[str, Any],
    external_index: dict[str, Player],
    name_school_index: dict[tuple[str, str], list[Player]],
) -> tuple[Player | None, str, str]:
    espn_player_id = str(row.get("ESPNPlayerID") or "")
    for external_id in (espn_player_id, f"espn:{espn_player_id}"):
        player = external_index.get(external_id)
        if player:
            return player, "external_id", "matched by provider player id"

    name_key = _identity(str(row.get("PlayerName") or ""))
    if not name_key:
        return None, "unmatched", "missing provider player name"
    for school_key in _school_keys(row):
        players = name_school_index.get((name_key, school_key), [])
        if len(players) == 1:
            return players[0], "name_school", "matched by normalized name and school"
        if len(players) > 1:
            return None, "duplicate_name_school", "duplicate local players share provider name and school"
    return None, "unmatched", "no local player matched provider row"


def upsert_espn_weekly_player_stats(
    db: Session,
    *,
    season: int,
    week: int,
    client: ESPNClient | None = None,
    record_job: bool = True,
) -> dict[str, int]:
    if record_job:
        return run_provider_sync_job(
            db,
            provider="espn",
            feed="player_game_stats_week",
            season=season,
            week=week,
            scope=f"season:{season}:week:{week}",
            operation=lambda: upsert_espn_weekly_player_stats(
                db,
                season=season,
                week=week,
                client=client,
                record_job=False,
            ),
        )

    espn = client or ESPNClient()
    summaries = espn.get_weekly_boxscore_summaries(season=season, week=week)
    rows = [row for summary in summaries for row in extract_player_box_score_stats(summary)]

    players = db.query(Player).all()
    external_index, name_school_index = _build_player_indexes(players)

    inserted = 0
    updated = 0
    skipped = 0
    for row in rows:
        try:
            ESPNPlayerStatPayload.validate_row(row)
        except ProviderPayloadValidationError as exc:
            record_unmatched_provider_row(
                db,
                provider="espn",
                season=season,
                week=week,
                row=row,
                reason=f"invalid provider payload: {exc}",
            )
            skipped += 1
            continue
        player, match_type, reason = _match_player(row, external_index, name_school_index)
        if not player:
            record_unmatched_provider_row(
                db,
                provider="espn",
                season=season,
                week=week,
                row=row,
                reason=reason,
            )
            skipped += 1
            continue
        record_provider_identity_audit(
            db,
            provider="espn",
            season=season,
            week=week,
            row=row,
            player_id=player.id,
            match_type=match_type,
            confidence=100 if match_type == "external_id" else 70,
        )
        stat = (
            db.query(PlayerStat)
            .filter(
                PlayerStat.player_id == player.id,
                PlayerStat.season == season,
                PlayerStat.week == week,
            )
            .first()
        )
        if not stat:
            stat = PlayerStat(player_id=player.id, season=season, week=week, source="espn", stats=row)
            db.add(stat)
            inserted += 1
        else:
            stat.source = "espn"
            stat.stats = row
            updated += 1

    db.commit()
    return {
        "events": len(summaries),
        "rows_seen": len(rows),
        "upserted": inserted + updated,
        "inserted": inserted,
        "updated": updated,
        "rows_inserted": inserted,
        "rows_updated": updated,
        "rows_rejected": skipped,
        "skipped": skipped,
    }
