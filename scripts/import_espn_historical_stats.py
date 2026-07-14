from __future__ import annotations

import argparse
from datetime import datetime, timezone

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.historical_stats import HistoricalStatImportRun
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.historical_stats import (
    fetch_and_store_player_history,
    resolve_espn_player_id,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import ESPN historical player season stats into the local cache.")
    parser.add_argument("--player-id", type=int, action="append", dest="player_ids", help="Import one player ID. Repeatable.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of mapped players to import.")
    parser.add_argument("--dry-run", action="store_true", help="Only report mapped player count; do not call ESPN or write rows.")
    parser.add_argument(
        "--ignore-feature-flag",
        action="store_true",
        help="Allow imports even when ESPN_HISTORICAL_STATS_ENABLED is false.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not settings.espn_historical_stats_enabled and not args.ignore_feature_flag and not args.dry_run:
        print("ESPN_HISTORICAL_STATS_ENABLED=false; pass --ignore-feature-flag to run this importer intentionally.")
        return 2

    db = SessionLocal()
    try:
        query = db.query(Player).order_by(Player.sheet_adp.asc().nullslast(), Player.id.asc())
        if args.player_ids:
            query = query.filter(Player.id.in_(args.player_ids))
        players = query.all()
        mapped_players = [player for player in players if resolve_espn_player_id(db, player)]
        if args.limit is not None:
            mapped_players = mapped_players[: max(0, args.limit)]

        if args.dry_run:
            print(f"Mapped players eligible for ESPN historical import: {len(mapped_players)}")
            return 0

        started_at = datetime.now(timezone.utc)
        run = HistoricalStatImportRun(
            provider="espn",
            requested_player_ids=[player.id for player in mapped_players],
            status="running",
            started_at=started_at,
            players_requested=len(mapped_players),
            trigger_type="manual",
        )
        db.add(run)
        db.commit()

        errors: dict[str, str] = {}
        for player in mapped_players:
            try:
                fetch_and_store_player_history(db, player)
                run.players_succeeded += 1
                db.commit()
            except Exception as exc:
                db.rollback()
                run = db.get(HistoricalStatImportRun, run.id)
                run.players_failed += 1
                errors[str(player.id)] = str(exc)
                db.commit()

        run = db.get(HistoricalStatImportRun, run.id)
        run.completed_at = datetime.now(timezone.utc)
        run.status = "completed_with_errors" if errors else "completed"
        run.error_summary = errors or None
        db.commit()
        print(
            f"ESPN historical import {run.status}: "
            f"{run.players_succeeded}/{run.players_requested} succeeded, {run.players_failed} failed"
        )
        return 1 if errors else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
