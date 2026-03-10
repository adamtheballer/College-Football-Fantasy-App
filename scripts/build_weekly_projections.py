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
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections
from collegefootballfantasy_api.app.services.projections.usage import compute_usage_shares


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly player projections.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--conference", type=str)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        players = session.scalars(select(Player)).all()

        stats_week = max(1, args.week - 1)
        stats_rows = session.scalars(
            select(PlayerStat).where(PlayerStat.season == args.season, PlayerStat.week == stats_week)
        ).all()
        player_stats = {row.player_id: row.stats for row in stats_rows}

        usage_rows = compute_usage_shares(players, player_stats, args.season, args.week)
        session.execute(
            delete(UsageShare).where(UsageShare.season == args.season, UsageShare.week == args.week)
        )
        session.add_all(usage_rows)
        session.commit()

        team_env_rows = session.scalars(
            select(TeamEnvironment).where(TeamEnvironment.season == args.season, TeamEnvironment.week == args.week)
        ).all()
        team_env_by_team = {row.team_name: row for row in team_env_rows}

        defense_rows = session.scalars(
            select(DefenseRating).where(DefenseRating.season == args.season, DefenseRating.week == args.week)
        ).all()
        defense_by_team = {row.team_name: row for row in defense_rows}

        injuries_rows = session.scalars(
            select(Injury).where(Injury.season == args.season, Injury.week == args.week)
        ).all()
        injuries_by_player = {row.player_id: row for row in injuries_rows}

        client = CFBDClient()
        games_rows = client.get_games_teams(args.season, args.week, conference=args.conference)
        opponent_by_team: dict[str, str] = {}
        for game in games_rows:
            teams = game.get("teams") or []
            if len(teams) != 2:
                continue
            team_a = teams[0].get("school")
            team_b = teams[1].get("school")
            if team_a and team_b:
                opponent_by_team[team_a] = team_b
                opponent_by_team[team_b] = team_a

        projections = build_weekly_projections(
            players=players,
            team_env_by_team=team_env_by_team,
            usage_by_player={row.player_id: row for row in usage_rows},
            defense_by_team=defense_by_team,
            player_stats=player_stats,
            injuries_by_player=injuries_by_player,
            opponent_by_team=opponent_by_team,
            season=args.season,
            week=args.week,
        )

        session.execute(
            delete(WeeklyProjection).where(
                WeeklyProjection.season == args.season, WeeklyProjection.week == args.week
            )
        )
        session.add_all(projections)
        session.commit()
        print(f"Stored {len(projections)} projections.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
