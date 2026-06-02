import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.crud.player_stat import upsert_player_stat
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models import load_model_registry
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.provider_cache import (
    get_or_create_sync_state,
    mark_sync_attempt,
    scope_dict_to_key,
)


def ingest_weekly_player_stats(session: Session, *, season: int, week: int) -> dict[str, int]:
    scope = {"season": season, "week": week}
    state = get_or_create_sync_state(
        session,
        provider="sportsdata",
        feed="player_game_stats_week",
        scope_key=scope_dict_to_key(scope),
    )
    mark_sync_attempt(session, state=state, status="syncing")
    session.commit()

    try:
        client = SportsDataClient()
        stats_rows = client.get_weekly_player_stats(season, week)
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
                season=season,
                week=week,
                stats=row,
                source="sportsdata",
                auto_commit=False,
            )
            created += 1

        state.meta = {
            "season": season,
            "week": week,
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
        return {"rows_seen": len(stats_rows), "upserted": created, "skipped": skipped}
    except Exception as exc:
        state = get_or_create_sync_state(
            session,
            provider="sportsdata",
            feed="player_game_stats_week",
            scope_key=scope_dict_to_key({"season": season, "week": week}),
        )
        mark_sync_attempt(session, state=state, status="failed", error_message=str(exc))
        session.commit()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest weekly player stats from SportsDataIO.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    load_model_registry()
    session = SessionLocal()
    try:
        result = ingest_weekly_player_stats(session, season=args.season, week=args.week)
        print(f"Ingested stats for {result['upserted']} players (skipped {result['skipped']}).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
