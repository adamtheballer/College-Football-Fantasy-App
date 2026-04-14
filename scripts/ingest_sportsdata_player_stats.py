import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.crud.player_stat import upsert_player_stat
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.provider_cache import (
    get_or_create_sync_state,
    mark_sync_attempt,
    scope_dict_to_key,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest weekly player stats from SportsDataIO.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        scope = {"season": args.season, "week": args.week}
        state = get_or_create_sync_state(
            session,
            provider="sportsdata",
            feed="player_game_stats_week",
            scope_key=scope_dict_to_key(scope),
        )
        mark_sync_attempt(session, state=state, status="syncing")
        session.commit()

        client = SportsDataClient()
        stats_rows = client.get_weekly_player_stats(args.season, args.week)
        players = session.scalars(select(Player)).all()
        player_index = {str(player.external_id): player for player in players if player.external_id}
        created = 0
        skipped = 0
        for row in stats_rows:
            external_id = row.get("PlayerID")
            if external_id is None:
                skipped += 1
                continue
            player = player_index.get(str(external_id))
            if not player:
                skipped += 1
                continue
            upsert_player_stat(
                session,
                player_id=player.id,
                season=args.season,
                week=args.week,
                stats=row,
                source="sportsdata",
            )
            created += 1

        state.meta = {
            "season": args.season,
            "week": args.week,
            "rows_seen": len(stats_rows),
            "upserted": created,
            "skipped": skipped,
        }
        mark_sync_attempt(
            session,
            state=state,
            status="ready",
            ttl_days=settings.sportsdata_cache_ttl_days,
        )
        session.commit()
        print(f"Ingested stats for {created} players (skipped {skipped}).")
    except Exception as exc:
        state = get_or_create_sync_state(
            session,
            provider="sportsdata",
            feed="player_game_stats_week",
            scope_key=scope_dict_to_key({"season": args.season, "week": args.week}),
        )
        mark_sync_attempt(session, state=state, status="failed", error_message=str(exc))
        session.commit()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
