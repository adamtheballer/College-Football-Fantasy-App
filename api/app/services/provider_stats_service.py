from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.espn_stats_sync import upsert_espn_weekly_player_stats
from collegefootballfantasy_api.app.services.provider_identity_audit import record_unmatched_provider_row


class StatsProvider(Protocol):
    name: str

    def sync_weekly_player_stats(self, db: Session, *, season: int, week: int) -> dict[str, int]:
        ...


def provider_player_id(row: dict[str, Any]) -> str | None:
    for key in ("PlayerID", "PlayerId", "player_id", "playerId", "ExternalID", "external_id"):
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return None


def upsert_sportsdata_weekly_player_stats(
    db: Session,
    *,
    season: int,
    week: int,
    client: SportsDataClient | None = None,
) -> dict[str, int]:
    sportsdata = client or SportsDataClient()
    rows = sportsdata.get_weekly_player_stats(season, week)
    players_by_external_id = {
        str(external_id): player
        for external_id, player in db.query(Player.external_id, Player).filter(Player.external_id.isnot(None)).all()
    }
    upserted = 0
    skipped = 0
    for row in rows:
        external_id = provider_player_id(row)
        if not external_id:
            record_unmatched_provider_row(
                db,
                provider="sportsdata",
                season=season,
                week=week,
                row=row,
                reason="missing provider player id",
            )
            skipped += 1
            continue
        player = players_by_external_id.get(external_id)
        if not player:
            record_unmatched_provider_row(
                db,
                provider="sportsdata",
                season=season,
                week=week,
                row=row,
                reason="no local player matched provider row",
            )
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
            stat = PlayerStat(player_id=player.id, season=season, week=week, source="sportsdata", stats=row)
            db.add(stat)
        else:
            stat.source = "sportsdata"
            stat.stats = row
        upserted += 1
    db.commit()
    return {"events": 0, "rows_seen": len(rows), "upserted": upserted, "skipped": skipped}


class ESPNStatsProvider:
    name = "espn"

    def sync_weekly_player_stats(self, db: Session, *, season: int, week: int) -> dict[str, int]:
        return upsert_espn_weekly_player_stats(db, season=season, week=week)


class SportsDataStatsProvider:
    name = "sportsdata"

    def sync_weekly_player_stats(self, db: Session, *, season: int, week: int) -> dict[str, int]:
        return upsert_sportsdata_weekly_player_stats(db, season=season, week=week)


def provider_for_name(provider: str) -> StatsProvider:
    if provider == "espn":
        return ESPNStatsProvider()
    if provider == "sportsdata":
        return SportsDataStatsProvider()
    raise ValueError(f"unsupported stats provider: {provider}")


def sync_provider_weekly_player_stats(db: Session, *, provider: str, season: int, week: int) -> dict[str, int]:
    return provider_for_name(provider).sync_weekly_player_stats(db, season=season, week=week)
