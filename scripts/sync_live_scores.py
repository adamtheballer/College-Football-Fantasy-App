from __future__ import annotations

import argparse
import time
from typing import Any

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.espn_stats_sync import upsert_espn_weekly_player_stats
from collegefootballfantasy_api.app.services.scoring_worker_service import RetryPolicy, run_scoring_worker_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync raw provider stats and recalculate live fantasy scores.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--league-id", type=int, default=None)
    parser.add_argument("--provider", choices=("sportsdata", "espn"), default="espn")
    parser.add_argument("--watch", action="store_true", help="Keep polling provider stats and recalculating scores.")
    parser.add_argument("--interval-seconds", type=int, default=90, help="Polling interval in seconds. Must be 1-90.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Provider sync attempts per run.")
    parser.add_argument("--backoff-seconds", type=float, default=2.0, help="Initial retry backoff in seconds.")
    parser.add_argument("--lock-ttl-seconds", type=int, default=300, help="Scoring job lock TTL in seconds.")
    parser.add_argument("--stale-run-seconds", type=int, default=900, help="Age before running scoring runs are marked stale.")
    parser.add_argument("--worker-id", type=str, default=None, help="Optional stable worker identifier.")
    args = parser.parse_args()
    if args.interval_seconds < 1 or args.interval_seconds > 90:
        raise SystemExit("--interval-seconds must be between 1 and 90.")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1.")
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


def run_once(args: argparse.Namespace) -> None:
    with SessionLocal() as db:
        result = run_scoring_worker_once(
            db,
            provider=args.provider,
            season=args.season,
            week=args.week,
            league_id=args.league_id,
            sync_provider_stats=lambda: upsert_provider_player_stats(args.provider, args.season, args.week),
            retry_policy=RetryPolicy(max_attempts=args.max_attempts, initial_backoff_seconds=args.backoff_seconds),
            lock_ttl_seconds=args.lock_ttl_seconds,
            stale_run_seconds=args.stale_run_seconds,
            worker_id=args.worker_id,
        )
    print(
        f"provider={args.provider} status={result.status} lock_acquired={result.lock_acquired} "
        f"run_id={result.run_id} retry_count={result.retry_count} "
        f"players_scored={result.players_updated} teams_scored={result.teams_updated} "
        f"matchups_updated={result.matchups_updated} message={result.message or ''}"
    )


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
