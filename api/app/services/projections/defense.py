from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.services.projections.constants import (
    PASS_DEF_MULTIPLIERS,
    RUSH_DEF_MULTIPLIERS,
    tier_from_percentile,
)


def _normalize_key(key: str) -> str:
    return "".join(ch for ch in key.lower() if ch.isalnum())


def _stats_to_map(stats: list[dict[str, Any]]) -> dict[str, float]:
    mapped: dict[str, float] = {}
    for row in stats:
        category = row.get("category") or row.get("name") or ""
        value = row.get("stat")
        if category and value is not None:
            try:
                mapped[_normalize_key(str(category))] = float(value)
            except (TypeError, ValueError):
                continue
    return mapped


def _stat_value(stats_map: dict[str, float], keys: list[str]) -> float:
    for key in keys:
        normalized = _normalize_key(key)
        if normalized in stats_map:
            return stats_map[normalized]
    return 0.0


def _z_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    avg = mean(values)
    std = pstdev(values)
    if std == 0:
        return [0.0 for _ in values]
    return [(value - avg) / std for value in values]


def compute_defense_ratings(games_teams_rows: list[dict[str, Any]], season: int, week: int) -> list[DefenseRating]:
    aggregates: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for game in games_teams_rows:
        teams = game.get("teams") or []
        if len(teams) != 2:
            continue
        team_a = teams[0]
        team_b = teams[1]
        name_a = team_a.get("school")
        name_b = team_b.get("school")
        if not name_a or not name_b:
            continue

        stats_a = _stats_to_map(team_a.get("stats") or [])
        stats_b = _stats_to_map(team_b.get("stats") or [])

        def add_allowed(def_team: str, off_stats: dict[str, float]) -> None:
            aggregates[def_team]["pass_yards_allowed"] += _stat_value(
                off_stats, ["passingYards", "passYards"]
            )
            aggregates[def_team]["pass_attempts_allowed"] += _stat_value(
                off_stats, ["passingAttempts", "passAttempts"]
            )
            aggregates[def_team]["pass_tds_allowed"] += _stat_value(
                off_stats, ["passingTDs", "passTDs", "passingTouchdowns"]
            )
            aggregates[def_team]["rush_yards_allowed"] += _stat_value(
                off_stats, ["rushingYards", "rushYards"]
            )
            aggregates[def_team]["rush_attempts_allowed"] += _stat_value(
                off_stats, ["rushingAttempts", "rushAttempts"]
            )
            aggregates[def_team]["rush_tds_allowed"] += _stat_value(
                off_stats, ["rushingTDs", "rushTDs", "rushingTouchdowns"]
            )
            aggregates[def_team]["sacks"] += _stat_value(off_stats, ["sacks"])
            aggregates[def_team]["interceptions"] += _stat_value(off_stats, ["interceptions", "ints"])

        add_allowed(name_a, stats_b)
        add_allowed(name_b, stats_a)

    teams = list(aggregates.keys())
    pass_ypa = []
    pass_td_rate = []
    sack_rate = []
    int_rate = []
    rush_ypc = []
    rush_td_rate = []

    for team in teams:
        row = aggregates[team]
        pass_attempts = max(row["pass_attempts_allowed"], 1.0)
        rush_attempts = max(row["rush_attempts_allowed"], 1.0)
        pass_ypa.append(row["pass_yards_allowed"] / pass_attempts)
        pass_td_rate.append(row["pass_tds_allowed"] / pass_attempts)
        sack_rate.append(row["sacks"] / pass_attempts)
        int_rate.append(row["interceptions"] / pass_attempts)
        rush_ypc.append(row["rush_yards_allowed"] / rush_attempts)
        rush_td_rate.append(row["rush_tds_allowed"] / rush_attempts)

    z_pass_ypa = _z_scores(pass_ypa)
    z_pass_td = _z_scores(pass_td_rate)
    z_sack = _z_scores(sack_rate)
    z_int = _z_scores(int_rate)
    z_rush_ypc = _z_scores(rush_ypc)
    z_rush_td = _z_scores(rush_td_rate)

    pass_scores = []
    rush_scores = []
    for idx, team in enumerate(teams):
        pass_score = (-0.40 * z_pass_ypa[idx]) + (-0.30 * z_pass_td[idx]) + (0.15 * z_sack[idx]) + (
            0.15 * z_int[idx]
        )
        rush_score = (-0.55 * z_rush_ypc[idx]) + (-0.35 * z_rush_td[idx]) + (0.10 * z_sack[idx])
        pass_scores.append(pass_score)
        rush_scores.append(rush_score)

    # percentile ranks
    sorted_pass = sorted(pass_scores)
    sorted_rush = sorted(rush_scores)

    ratings: list[DefenseRating] = []
    for idx, team in enumerate(teams):
        pass_percentile = (sorted_pass.index(pass_scores[idx]) + 1) / len(sorted_pass)
        rush_percentile = (sorted_rush.index(rush_scores[idx]) + 1) / len(sorted_rush)

        pass_tier = tier_from_percentile(pass_percentile)
        rush_tier = tier_from_percentile(rush_percentile)

        pass_mult = PASS_DEF_MULTIPLIERS[pass_tier]
        rush_mult = RUSH_DEF_MULTIPLIERS[rush_tier]

        ratings.append(
            DefenseRating(
                team_name=team,
                season=season,
                week=week,
                pass_def_score=pass_scores[idx],
                rush_def_score=rush_scores[idx],
                pass_def_tier=pass_tier,
                rush_def_tier=rush_tier,
                pass_yards_multiplier=pass_mult.yards,
                pass_catch_multiplier=pass_mult.catch,
                pass_td_multiplier=pass_mult.td,
                pass_turnover_multiplier=pass_mult.turnover,
                rush_yards_multiplier=rush_mult.yards,
                rush_success_multiplier=rush_mult.catch,
                rush_td_multiplier=rush_mult.td,
            )
        )

    return ratings
