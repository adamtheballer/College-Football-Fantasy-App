from __future__ import annotations

import argparse
import time

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models import league, roster, team, user
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.espn_player_lookup import resolve_espn_player_by_name
from collegefootballfantasy_api.app.services.historical_stats import resolve_espn_player_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create trusted ESPN player identity mappings from exact profile matches.")
    parser.add_argument("--player-id", type=int, action="append", dest="player_ids", help="Sync one player ID. Repeatable.")
    parser.add_argument("--limit", type=int, default=None, help="Limit unresolved players considered.")
    parser.add_argument("--dry-run", action="store_true", help="Report unresolved player count without contacting ESPN.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        query = db.query(Player).order_by(Player.sheet_adp.asc().nullslast(), Player.id.asc())
        if args.player_ids:
            query = query.filter(Player.id.in_(args.player_ids))
        players = query.all()
        unresolved = [player for player in players if not resolve_espn_player_id(db, player)]
        if args.limit is not None:
            unresolved = unresolved[: max(0, args.limit)]

        if args.dry_run:
            print(f"Players needing trusted ESPN identity mappings: {len(unresolved)}")
            return 0

        matched = 0
        unmatched = 0
        failed = 0
        delay_seconds = 1 / max(settings.espn_historical_stats_requests_per_second, 0.1)
        for index, player in enumerate(unresolved):
            try:
                if resolve_espn_player_by_name(db, player):
                    matched += 1
                else:
                    unmatched += 1
            except Exception as exc:
                db.rollback()
                failed += 1
                print(f"Failed ESPN identity lookup for player {player.id} ({player.name}): {exc}")
            if index < len(unresolved) - 1:
                time.sleep(delay_seconds)

        print(
            "ESPN identity sync complete: "
            f"{matched} matched, {unmatched} unmatched, {failed} failed, {len(unresolved)} considered"
        )
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
