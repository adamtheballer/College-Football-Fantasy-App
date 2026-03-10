from __future__ import annotations

from collections import defaultdict
from typing import Any

from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.services.projections.defense import _stat_value, _stats_to_map


def compute_team_environment(
    games_teams_rows: list[dict[str, Any]],
    season: int,
    week: int,
    implied_totals: dict[str, float] | None = None,
    spreads: dict[str, float] | None = None,
) -> list[TeamEnvironment]:
    implied_totals = implied_totals or {}
    spreads = spreads or {}
    aggregates: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    games_played: dict[str, int] = defaultdict(int)

    for game in games_teams_rows:
        teams = game.get("teams") or []
        if len(teams) != 2:
            continue
        for team in teams:
            name = team.get("school")
            if not name:
                continue
            stats_map = _stats_to_map(team.get("stats") or [])
            plays = _stat_value(stats_map, ["plays", "totalPlays"])
            pass_attempts = _stat_value(stats_map, ["passingAttempts", "passAttempts"])
            rush_attempts = _stat_value(stats_map, ["rushingAttempts", "rushAttempts"])
            points = _stat_value(stats_map, ["points", "score"])
            red_zone = _stat_value(stats_map, ["redZoneAttempts", "redZoneTrips", "redZonePossessions"])
            red_zone_tds = _stat_value(stats_map, ["redZoneTDs", "redZoneTouchdowns"])

            aggregates[name]["plays"] += plays
            aggregates[name]["pass_attempts"] += pass_attempts
            aggregates[name]["rush_attempts"] += rush_attempts
            aggregates[name]["points"] += points
            aggregates[name]["red_zone_trips"] += red_zone
            aggregates[name]["red_zone_tds"] += red_zone_tds
            games_played[name] += 1

    environments: list[TeamEnvironment] = []
    for team_name, stats in aggregates.items():
        gp = max(games_played[team_name], 1)
        plays_pg = stats["plays"] / gp if stats["plays"] else (stats["pass_attempts"] + stats["rush_attempts"]) / gp
        pass_rate = stats["pass_attempts"] / max(stats["pass_attempts"] + stats["rush_attempts"], 1.0)
        rush_rate = 1.0 - pass_rate
        points_pg = stats["points"] / gp
        red_zone_trips_pg = stats["red_zone_trips"] / gp if stats["red_zone_trips"] else 0.0
        red_zone_td_rate = stats["red_zone_tds"] / max(stats["red_zone_trips"], 1.0)

        expected_plays = plays_pg
        implied_total = implied_totals.get(team_name)
        if implied_total is not None:
            expected_points = 0.6 * points_pg + 0.4 * implied_total
        else:
            expected_points = points_pg

        environments.append(
            TeamEnvironment(
                team_name=team_name,
                season=season,
                week=week,
                expected_plays=round(expected_plays, 2),
                expected_points=round(expected_points, 2),
                pass_rate=round(pass_rate, 4),
                rush_rate=round(rush_rate, 4),
                red_zone_trips=round(red_zone_trips_pg, 2),
                red_zone_td_rate=round(red_zone_td_rate, 4),
                pace_seconds_per_play=0.0,
                implied_team_total=implied_total,
                spread=spreads.get(team_name),
            )
        )

    return environments
