from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Any

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.services.espn_stats_sync import upsert_espn_weekly_player_stats
from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync raw provider stats and recalculate live fantasy scores.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--league-id", type=int, default=None)
    parser.add_argument("--provider", choices=("sportsdata", "espn"), default="espn")
    parser.add_argument("--watch", action="store_true", help="Keep polling provider stats and recalculating scores.")
    parser.add_argument("--interval-seconds", type=int, default=90, help="Polling interval in seconds. Must be 1-90.")
    args = parser.parse_args()
    if args.interval_seconds < 1 or args.interval_seconds > 90:
        raise SystemExit("--interval-seconds must be between 1 and 90.")
    return args


def provider_player_id(row: dict[str, Any]) -> str | None:
    for key in ("PlayerID", "PlayerId", "player_id", "playerId", "ExternalID", "external_id"):
        value = row.get(key)
        if value is not None and value != "":
            return str(value)
    return None


def upsert_player_stats(season: int, week: int) -> int:
    client = SportsDataClient()
    rows = client.get_weekly_player_stats(season, week)
    updated = 0
    with SessionLocal() as db:
        players_by_external_id = {
            str(external_id): player
            for external_id, player in db.query(Player.external_id, Player).filter(Player.external_id.isnot(None)).all()
        }
        for row in rows:
            external_id = provider_player_id(row)
            if not external_id:
                continue
            player = players_by_external_id.get(external_id)
            if not player:
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
                stat = PlayerStat(
                    player_id=player.id,
                    season=season,
                    week=week,
                    source="sportsdata",
                    stats=row,
                )
                db.add(stat)
            else:
                stat.source = "sportsdata"
                stat.stats = row
            updated += 1
        db.commit()
    return updated


def upsert_provider_player_stats(provider: str, season: int, week: int) -> dict[str, int]:
    if provider == "espn":
        with SessionLocal() as db:
            return upsert_espn_weekly_player_stats(db, season=season, week=week)
    updated = upsert_player_stats(season, week)
    return {"rows_seen": updated, "upserted": updated, "skipped": 0, "events": 0}


def target_league_ids(season: int, league_id: int | None) -> list[int]:
    with SessionLocal() as db:
        if league_id is not None:
            league = db.get(League, league_id)
            if not league:
                raise SystemExit(f"league {league_id} not found")
            return [league.id]
        return [
            league.id
            for league in db.query(League).filter(League.season_year == season).order_by(League.id.asc()).all()
        ]


def record_global_failure(provider: str, season: int, week: int, league_id: int | None, error: Exception) -> None:
    with SessionLocal() as db:
        run = ScoringRun(
            league_id=league_id,
            season=season,
            week=week,
            provider=provider,
            status="failed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            error_message=str(error)[:1000],
        )
        db.add(run)
        db.commit()


def run_once(args: argparse.Namespace) -> None:
    try:
        sync_result = upsert_provider_player_stats(args.provider, args.season, args.week)
        totals = {"players": 0, "teams": 0, "matchups": 0}
        for league_id in target_league_ids(args.season, args.league_id):
            with SessionLocal() as db:
                summary = run_league_scoring_recalculation(
                    db,
                    league_id=league_id,
                    season=args.season,
                    week=args.week,
                    provider=args.provider,
                )
                totals["players"] += summary.players_scored
                totals["teams"] += summary.teams_scored
                totals["matchups"] += summary.matchups_updated
        print(
            f"provider={args.provider} stats_upserted={sync_result['upserted']} "
            f"rows_seen={sync_result['rows_seen']} skipped={sync_result['skipped']} "
            f"events={sync_result['events']} players_scored={totals['players']} "
            f"teams_scored={totals['teams']} matchups_updated={totals['matchups']}"
        )
    except Exception as exc:
        record_global_failure(args.provider, args.season, args.week, args.league_id, exc)
        raise


def main() -> None:
    args = parse_args()
    if not args.watch:
        run_once(args)
        return
    while True:
        started_at = time.monotonic()
        run_once(args)
        elapsed = time.monotonic() - started_at
        time.sleep(max(0, args.interval_seconds - elapsed))


if __name__ == "__main__":
    main()
