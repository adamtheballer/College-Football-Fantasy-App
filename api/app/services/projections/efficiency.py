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


# One game's efficiency shrinks toward the existing position baselines.
# Prior sample sizes represent roughly one game's opportunities, keeping a
# single long play from being extrapolated across a full starter workload.
PASSING_PRIOR_ATTEMPTS = 30.0
RUSHING_PRIOR_ATTEMPTS = 15.0
RECEIVING_PRIOR_TARGETS = 8.0


def _smoothed_rate(total: float, opportunities: float, prior: float, prior_opportunities: float) -> float:
    return (total + prior * prior_opportunities) / (opportunities + prior_opportunities)


def compute_efficiency(stats: dict[str, Any], position: str) -> dict[str, float]:
    pos = position.upper()
    rushing_attempts = _stat_value(stats, ["RushingAttempts", "RushAttempts", "rushing_attempts", "rush_attempts"])
    rushing_yards = _stat_value(stats, ["RushingYards", "RushYards", "rush_yards", "rushing_yards"])
    targets = _stat_value(stats, ["ReceivingTargets", "Targets", "targets", "receiving_targets"])
    receptions = _stat_value(stats, ["Receptions", "receptions"])
    receiving_yards = _stat_value(stats, ["ReceivingYards", "RecYards", "rec_yards", "receiving_yards"])
    passing_attempts = _stat_value(stats, ["PassingAttempts", "PassAttempts", "passing_attempts", "pass_attempts"])
    passing_completions = _stat_value(stats, ["PassingCompletions", "PassCompletions", "Completions", "completions", "passing_completions"])
    passing_yards = _stat_value(stats, ["PassingYards", "PassYards", "pass_yards", "passing_yards"])
    passing_tds = _stat_value(stats, ["PassingTouchdowns", "PassTDs", "pass_tds", "passing_tds"])
    passing_ints = _stat_value(stats, ["Interceptions", "PassingInterceptions", "interceptions", "passing_interceptions"])

    receiving_efficiency = {}
    if targets > 0:
        prior_ypt, prior_catch_rate = {
            "RB": (6.5, 0.72), "WR": (8.5, 0.62), "TE": (7.5, 0.68),
        }.get(pos, (8.5, 0.62))
        receiving_efficiency = {
            "ypt": _smoothed_rate(receiving_yards, targets, prior_ypt, RECEIVING_PRIOR_TARGETS),
            "catch_rate": min(1.0, _smoothed_rate(receptions, targets, prior_catch_rate, RECEIVING_PRIOR_TARGETS)),
        }

    if pos == "QB":
        values: dict[str, float] = {}
        if passing_attempts > 0:
            values.update(
                {
                    "comp_pct": _smoothed_rate(passing_completions, passing_attempts, 0.62, PASSING_PRIOR_ATTEMPTS),
                    "ypa": _smoothed_rate(passing_yards, passing_attempts, 7.5, PASSING_PRIOR_ATTEMPTS),
                    "pass_td_rate": _smoothed_rate(passing_tds, passing_attempts, 0.05, PASSING_PRIOR_ATTEMPTS),
                    "int_rate": _smoothed_rate(passing_ints, passing_attempts, 0.02, PASSING_PRIOR_ATTEMPTS),
                }
            )
        if rushing_attempts > 0:
            values["rush_ypc"] = _smoothed_rate(rushing_yards, rushing_attempts, 4.5, RUSHING_PRIOR_ATTEMPTS)
        return values
    if pos == "RB":
        values = {}
        if rushing_attempts > 0:
            values["ypc"] = _smoothed_rate(rushing_yards, rushing_attempts, 4.5, RUSHING_PRIOR_ATTEMPTS)
        if targets > 0:
            values.update(receiving_efficiency)
        return values
    if pos in {"WR", "TE"}:
        if targets <= 0:
            return {}
        return receiving_efficiency
    if pos == "K":
        return {}
    values = {}
    if rushing_attempts > 0:
        values["ypc"] = _smoothed_rate(rushing_yards, rushing_attempts, 4.5, RUSHING_PRIOR_ATTEMPTS)
    if targets > 0:
        values.update(receiving_efficiency)
    return values
