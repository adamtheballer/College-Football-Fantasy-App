import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.crud.player_stat import upsert_player_stat
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.sportsdata import SportsDataClient
from collegefootballfantasy_api.app.models.player import Player


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest weekly player stats from SportsDataIO.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    client = SportsDataClient()
    stats_rows = client.get_weekly_player_stats(args.season, args.week)

    session = SessionLocal()
    try:
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
        print(f"Ingested stats for {created} players (skipped {skipped}).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
