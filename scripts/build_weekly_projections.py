import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime
from numbers import Number

from sqlalchemy import and_, delete, or_, select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from api.app.db.session import SessionLocal
from api.app.integrations.cfbd import CFBDClient
from api.app.models import load_model_registry
from api.app.models.defense_rating import DefenseRating
from api.app.models.injury import Injury
from api.app.models.player import Player
from api.app.models.player_stat import PlayerStat
from api.app.models.team_environment import TeamEnvironment
from api.app.models.usage_share import UsageShare
from api.app.models.weekly_projection import WeeklyProjection
from api.app.services.projections.engine import build_weekly_projections
from api.app.services.projections.usage import compute_usage_shares


AGGREGATE_STAT_KEYS = [
    "PassingAttempts",
    "PassingCompletions",
    "PassingYards",
    "PassingTouchdowns",
    "PassingInterceptions",
    "RushingAttempts",
    "RushingYards",
    "RushingTouchdowns",
    "Receptions",
    "ReceivingYards",
    "ReceivingTouchdowns",
    "ReceivingTargets",
    "Targets",
]


def _safe_float(value: object) -> float:
    try:
        if isinstance(value, Number):
            return float(value)
        if isinstance(value, str):
            return float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0


def _aggregate_player_stats(rows: list[PlayerStat], season: int) -> dict[int, dict]:
    by_player: dict[int, list[PlayerStat]] = defaultdict(list)
    for row in rows:
        by_player[row.player_id].append(row)

    aggregated: dict[int, dict] = {}
    for player_id, player_rows in by_player.items():
        season_rows = [row for row in player_rows if row.season == season]
        scoped_rows = season_rows if season_rows else player_rows
        combined: dict[str, object] = {}
        for key in AGGREGATE_STAT_KEYS:
            total = sum(_safe_float((row.stats or {}).get(key)) for row in scoped_rows)
            if total > 0:
                combined[key] = total
        if combined:
            combined["Games"] = len(scoped_rows)
            aggregated[player_id] = combined
    return aggregated


def main() -> None:
    parser = argparse.ArgumentParser(description="Build weekly player projections.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--conference", type=str)
    args = parser.parse_args()

    load_model_registry()
    session = SessionLocal()
    try:
        players = session.scalars(select(Player)).all()

        stats_week = max(1, args.week - 1)
        stats_rows = session.scalars(
            select(PlayerStat).where(PlayerStat.season == args.season, PlayerStat.week == stats_week)
        ).all()
        if not stats_rows:
            historical_rows = session.scalars(
                select(PlayerStat)
                .where(
                    or_(
                        PlayerStat.season < args.season,
                        and_(PlayerStat.season == args.season, PlayerStat.week < args.week),
                    )
                )
                .order_by(PlayerStat.season.desc(), PlayerStat.week.desc(), PlayerStat.id.desc())
            ).all()
            player_stats = _aggregate_player_stats(historical_rows, season=max(args.season - 1, 0))
        else:
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
