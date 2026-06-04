import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import delete

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from api.app.db.session import SessionLocal
from api.app.integrations.cfbd import CFBDClient
from api.app.models import load_model_registry
from api.app.models.defense_rating import DefenseRating
from api.app.services.projections.defense import compute_defense_ratings
from api.app.services.power4 import list_power4_teams


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly defense ratings from CFBD.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--conference", type=str)
    args = parser.parse_args()

    load_model_registry()
    client = CFBDClient()
    games_rows = client.get_games_teams(args.season, args.week, conference=args.conference)
    ratings = compute_defense_ratings(games_rows, season=args.season, week=args.week)
    if not ratings:
        ratings = [
            DefenseRating(
                team_name=team,
                season=args.season,
                week=args.week,
                pass_def_score=0.0,
                rush_def_score=0.0,
                pass_def_tier="Average",
                rush_def_tier="Average",
                pass_yards_multiplier=1.0,
                pass_catch_multiplier=1.0,
                pass_td_multiplier=1.0,
                pass_turnover_multiplier=1.0,
                rush_yards_multiplier=1.0,
                rush_success_multiplier=1.0,
                rush_td_multiplier=1.0,
            )
            for team in list_power4_teams()
        ]

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
