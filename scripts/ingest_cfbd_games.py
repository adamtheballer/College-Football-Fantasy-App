import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.cfbd import CFBDClient
from collegefootballfantasy_api.app.models.game import Game


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CFB games from CFBD.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--conference", type=str)
    args = parser.parse_args()

    client = CFBDClient()
    games_rows = client.get_games_teams(args.season, args.week, conference=args.conference)

    session = SessionLocal()
    try:
        created = 0
        for row in games_rows:
            external_id = row.get("id") or row.get("gameId")
            home_team = row.get("homeTeam") or row.get("home_team")
            away_team = row.get("awayTeam") or row.get("away_team")
            if not home_team or not away_team:
                continue

            existing = None
            if external_id:
                existing = session.scalar(select(Game).where(Game.external_id == str(external_id)))

            if existing:
                game = existing
            else:
                game = Game(external_id=str(external_id) if external_id else None, season=args.season, week=args.week)

            game.season_type = row.get("seasonType") or row.get("season_type") or "regular"
            start_date = row.get("startDate") or row.get("start_date")
            if isinstance(start_date, str):
                try:
                    start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                except ValueError:
                    start_date = None
            game.start_date = start_date
            game.home_team = home_team
            game.away_team = away_team
            game.home_points = row.get("homePoints")
            game.away_points = row.get("awayPoints")
            game.neutral_site = bool(row.get("neutralSite") or row.get("neutral_site") or False)

            session.add(game)
            created += 1

        session.commit()
        print(f"Ingested {created} games.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
