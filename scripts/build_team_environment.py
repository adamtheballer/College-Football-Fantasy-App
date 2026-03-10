import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import delete, select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.cfbd import CFBDClient
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.game_odds import GameOdds
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.services.projections.team_environment import compute_team_environment


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly team environment baselines from CFBD.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--conference", type=str)
    args = parser.parse_args()

    client = CFBDClient()
    games_rows = client.get_games_teams(args.season, args.week, conference=args.conference)
    implied_totals: dict[str, float] = {}
    spreads: dict[str, float] = {}
    session = SessionLocal()
    try:
        games = session.scalars(
            select(Game).where(Game.season == args.season, Game.week == args.week)
        ).all()
        game_ids = [g.id for g in games]
        odds_rows = session.scalars(select(GameOdds).where(GameOdds.game_id.in_(game_ids))).all()
        odds_by_game = {row.game_id: row for row in odds_rows}
        for game in games:
            odds = odds_by_game.get(game.id)
            if not odds:
                continue
            if odds.home_implied is not None:
                implied_totals[game.home_team] = odds.home_implied
            if odds.away_implied is not None:
                implied_totals[game.away_team] = odds.away_implied
            if odds.spread is not None:
                spreads[game.home_team] = odds.spread
                spreads[game.away_team] = -odds.spread
    finally:
        session.close()

    environments = compute_team_environment(
        games_rows,
        season=args.season,
        week=args.week,
        implied_totals=implied_totals,
        spreads=spreads,
    )

    session = SessionLocal()
    try:
        session.execute(
            delete(TeamEnvironment).where(TeamEnvironment.season == args.season, TeamEnvironment.week == args.week)
        )
        session.add_all(environments)
        session.commit()
        print(f"Stored {len(environments)} team environment rows.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
