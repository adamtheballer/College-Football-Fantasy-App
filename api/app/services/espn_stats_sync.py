from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import ESPNClient, extract_player_box_score_stats
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat


def _identity(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _school_keys(row: dict[str, Any]) -> set[str]:
    keys = {_identity(str(row.get("School") or "")), _identity(str(row.get("Team") or ""))}
    aliases = row.get("TeamAliases")
    if isinstance(aliases, list):
        keys.update(_identity(str(alias)) for alias in aliases)
    return {key for key in keys if key}


def _build_player_indexes(players: list[Player]) -> tuple[dict[str, Player], dict[tuple[str, str], Player]]:
    external_index: dict[str, Player] = {}
    name_school_index: dict[tuple[str, str], Player] = {}
    for player in players:
        if player.external_id:
            external_id = str(player.external_id)
            external_index[external_id] = player
            external_index[external_id.removeprefix("espn:")] = player
        name_key = _identity(player.name)
        school_key = _identity(player.school)
        if name_key and school_key:
            name_school_index[(name_key, school_key)] = player
    return external_index, name_school_index


def _match_player(
    row: dict[str, Any],
    external_index: dict[str, Player],
    name_school_index: dict[tuple[str, str], Player],
) -> Player | None:
    espn_player_id = str(row.get("ESPNPlayerID") or "")
    for external_id in (espn_player_id, f"espn:{espn_player_id}"):
        player = external_index.get(external_id)
        if player:
            return player

    name_key = _identity(str(row.get("PlayerName") or ""))
    if not name_key:
        return None
    for school_key in _school_keys(row):
        player = name_school_index.get((name_key, school_key))
        if player:
            return player
    return None


def upsert_espn_weekly_player_stats(
    db: Session,
    *,
    season: int,
    week: int,
    client: ESPNClient | None = None,
) -> dict[str, int]:
    espn = client or ESPNClient()
    summaries = espn.get_weekly_boxscore_summaries(season=season, week=week)
    rows = [row for summary in summaries for row in extract_player_box_score_stats(summary)]

    players = db.query(Player).all()
    external_index, name_school_index = _build_player_indexes(players)

    upserted = 0
    skipped = 0
    for row in rows:
        player = _match_player(row, external_index, name_school_index)
        if not player:
            skipped += 1
            continue
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
        else:
            stat.source = "espn"
            stat.stats = row
        upserted += 1

    db.commit()
    return {
        "events": len(summaries),
        "rows_seen": len(rows),
        "upserted": upserted,
        "skipped": skipped,
    }
