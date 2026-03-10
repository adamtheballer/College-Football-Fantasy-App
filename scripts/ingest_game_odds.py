import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.odds_api import OddsApiClient
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.game_odds import GameOdds


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _extract_spread(bookmakers: list[dict], home_team: str) -> float | None:
    spreads: list[float] = []
    for bookmaker in bookmakers or []:
        for market in bookmaker.get("markets", []):
            if market.get("key") != "spreads":
                continue
            for outcome in market.get("outcomes", []):
                if outcome.get("name") == home_team and outcome.get("point") is not None:
                    spreads.append(float(outcome["point"]))
    return _average(spreads)


def _extract_total(bookmakers: list[dict]) -> float | None:
    totals: list[float] = []
    for bookmaker in bookmakers or []:
        for market in bookmaker.get("markets", []):
            if market.get("key") != "totals":
                continue
            for outcome in market.get("outcomes", []):
                if outcome.get("point") is not None:
                    totals.append(float(outcome["point"]))
    return _average(totals)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest game odds from The Odds API.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    client = OddsApiClient()
    odds_rows = client.get_odds()

    session = SessionLocal()
    try:
        games = session.scalars(select(Game).where(Game.season == args.season, Game.week == args.week)).all()
        game_index = {(g.home_team.lower(), g.away_team.lower()): g for g in games}

        created = 0
        for row in odds_rows:
            home_team = row.get("home_team")
            away_team = row.get("away_team")
            if not home_team or not away_team:
                continue

            game = game_index.get((home_team.lower(), away_team.lower()))
            if not game:
                continue

            spread = _extract_spread(row.get("bookmakers", []), home_team)
            total = _extract_total(row.get("bookmakers", []))

            if total is not None and spread is not None:
                home_implied = (total / 2) - (spread / 2)
                away_implied = (total / 2) + (spread / 2)
            else:
                home_implied = None
                away_implied = None

            odds = GameOdds(
                game_id=game.id,
                season=args.season,
                week=args.week,
                source="oddsapi",
                spread=spread,
                over_under=total,
                home_implied=home_implied,
                away_implied=away_implied,
            )
            session.add(odds)
            created += 1

        session.commit()
        print(f"Ingested {created} game odds.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
