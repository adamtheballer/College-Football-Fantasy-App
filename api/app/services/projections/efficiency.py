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

    ypc = rushing_yards / max(rushing_attempts, 1.0)
    ypt = receiving_yards / max(targets, 1.0)
    catch_rate = receptions / max(targets, 1.0)
    ypa = passing_yards / max(passing_attempts, 1.0)
    pass_td_rate = passing_tds / max(passing_attempts, 1.0)
    int_rate = passing_ints / max(passing_attempts, 1.0)
    comp_pct = passing_completions / max(passing_attempts, 1.0)

    if pos == "QB":
        return {
            "comp_pct": comp_pct,
            "ypa": ypa,
            "pass_td_rate": pass_td_rate,
            "int_rate": int_rate,
            "rush_ypc": ypc,
        }
    if pos == "RB":
        return {
            "ypc": ypc,
            "ypt": ypt,
            "catch_rate": catch_rate,
        }
    if pos in {"WR", "TE"}:
        return {
            "ypt": ypt,
            "catch_rate": catch_rate,
        }
    if pos == "K":
        return {}
    return {
        "ypc": ypc,
        "ypt": ypt,
        "catch_rate": catch_rate,
    }
