from __future__ import annotations

from typing import Any


def _stat_value(stats: dict[str, Any], keys: list[str]) -> float:
    for key in keys:
        if key in stats and stats[key] is not None:
            try:
                return float(stats[key])
            except (TypeError, ValueError):
                continue
    return 0.0


def compute_efficiency(stats: dict[str, Any], position: str) -> dict[str, float]:
    pos = position.upper()
    rushing_attempts = _stat_value(stats, ["RushingAttempts", "RushAttempts"])
    rushing_yards = _stat_value(stats, ["RushingYards", "RushYards"])
    targets = _stat_value(stats, ["ReceivingTargets", "Targets"])
    receptions = _stat_value(stats, ["Receptions"])
    receiving_yards = _stat_value(stats, ["ReceivingYards", "RecYards"])
    passing_attempts = _stat_value(stats, ["PassingAttempts", "PassAttempts"])
    passing_completions = _stat_value(stats, ["PassingCompletions", "PassCompletions", "Completions"])
    passing_yards = _stat_value(stats, ["PassingYards", "PassYards"])
    passing_tds = _stat_value(stats, ["PassingTouchdowns", "PassTDs"])
    passing_ints = _stat_value(stats, ["Interceptions", "PassingInterceptions"])

    if pos == "QB":
        values: dict[str, float] = {}
        if passing_attempts > 0:
            values.update(
                {
                    "comp_pct": passing_completions / passing_attempts,
                    "ypa": passing_yards / passing_attempts,
                    "pass_td_rate": passing_tds / passing_attempts,
                    "int_rate": passing_ints / passing_attempts,
                }
            )
        if rushing_attempts > 0:
            values["rush_ypc"] = rushing_yards / rushing_attempts
        return values
    if pos == "RB":
        values = {}
        if rushing_attempts > 0:
            values["ypc"] = rushing_yards / rushing_attempts
        if targets > 0:
            values.update({"ypt": receiving_yards / targets, "catch_rate": receptions / targets})
        return values
    if pos in {"WR", "TE"}:
        if targets <= 0:
            return {}
        return {"ypt": receiving_yards / targets, "catch_rate": receptions / targets}
    if pos == "K":
        return {}
    values = {}
    if rushing_attempts > 0:
        values["ypc"] = rushing_yards / rushing_attempts
    if targets > 0:
        values.update({"ypt": receiving_yards / targets, "catch_rate": receptions / targets})
    return values
