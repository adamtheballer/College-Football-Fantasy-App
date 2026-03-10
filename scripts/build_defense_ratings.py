import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import delete

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.cfbd import CFBDClient
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.services.projections.defense import compute_defense_ratings


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly defense ratings from CFBD.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--conference", type=str)
    args = parser.parse_args()

    client = CFBDClient()
    games_rows = client.get_games_teams(args.season, args.week, conference=args.conference)
    ratings = compute_defense_ratings(games_rows, season=args.season, week=args.week)

    session = SessionLocal()
    try:
        session.execute(
            delete(DefenseRating).where(DefenseRating.season == args.season, DefenseRating.week == args.week)
        )
        session.add_all(ratings)
        session.commit()
        print(f"Stored {len(ratings)} defense ratings.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
