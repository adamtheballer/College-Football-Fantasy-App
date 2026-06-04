from __future__ import annotations

from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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
        out: dict[str, float] = {}
        if passing_attempts >= 15:
            out["comp_pct"] = _clamp(passing_completions / passing_attempts, 0.45, 0.80)
            out["ypa"] = _clamp(passing_yards / passing_attempts, 4.5, 12.0)
            out["pass_td_rate"] = _clamp(passing_tds / passing_attempts, 0.015, 0.12)
            out["int_rate"] = _clamp(passing_ints / passing_attempts, 0.0, 0.08)
        if rushing_attempts >= 8:
            out["rush_ypc"] = _clamp(rushing_yards / rushing_attempts, 2.5, 9.0)
        return out

    if pos == "RB":
        out: dict[str, float] = {}
        if rushing_attempts >= 12:
            out["ypc"] = _clamp(rushing_yards / rushing_attempts, 2.5, 8.0)
        if targets >= 8:
            out["ypt"] = _clamp(receiving_yards / targets, 3.0, 14.0)
            out["catch_rate"] = _clamp(receptions / targets, 0.45, 0.95)
        return out

    if pos in {"WR", "TE"}:
        if targets >= 10:
            return {
                "ypt": _clamp(receiving_yards / targets, 4.0, 16.0),
                "catch_rate": _clamp(receptions / targets, 0.40, 0.92),
            }
        return {}

    if pos == "K":
        return {}
    return {}
