from __future__ import annotations

from collections.abc import Iterable

from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.defense_vs_position import DefenseVsPosition


def grade_from_rank(rank: int) -> str:
    if rank >= 110:
        return "A+"
    if rank >= 90:
        return "A"
    if rank >= 70:
        return "B"
    if rank >= 50:
        return "C"
    if rank >= 30:
        return "D"
    return "F"


def estimate_rank_from_tier(tier: str, score: float | None = None) -> int:
    tier = (tier or "Average").lower()
    ranges = {
        "elite": (1, 15),
        "strong": (16, 40),
        "average": (41, 90),
        "weak": (91, 110),
        "bad": (111, 130),
    }
    low, high = ranges.get(tier, (50, 80))
    if score is None:
        return int((low + high) / 2)
    scale = min(max(score, 0), 100) / 100
    return int(low + (high - low) * (1 - scale))


def derive_from_defense(
    defense: DefenseRating,
    position: str,
    league_ratings: Iterable[DefenseRating] | None = None,
) -> dict:
    position = position.upper()
    is_pass = position in {"QB", "WR", "TE"}
    tier = defense.pass_def_tier if is_pass else defense.rush_def_tier
    score = defense.pass_def_score if is_pass else defense.rush_def_score
    rank = estimate_rank_from_tier(tier, score)

    baseline_ypt = 7.5
    baseline_ypc = 4.2
    yards_per_target = baseline_ypt * defense.pass_yards_multiplier
    yards_per_rush = baseline_ypc * defense.rush_yards_multiplier
    pressure_rate = 0.22 * defense.pass_turnover_multiplier
    pass_td_rate = 0.035 * defense.pass_td_multiplier
    rush_td_rate = 0.03 * defense.rush_td_multiplier
    explosive_rate = 0.1 * defense.pass_yards_multiplier

    return {
        "grade": grade_from_rank(rank),
        "rank": rank,
        "yards_per_target": round(yards_per_target, 2),
        "yards_per_rush": round(yards_per_rush, 2),
        "pressure_rate": round(pressure_rate, 2),
        "pass_td_rate": round(pass_td_rate, 3),
        "rush_td_rate": round(rush_td_rate, 3),
        "explosive_rate": round(explosive_rate, 3),
    }


def build_matchup_row(
    team: str,
    season: int,
    week: int,
    position: str,
    defense: DefenseRating | None,
    cached: DefenseVsPosition | None,
) -> dict:
    if cached:
        return {
            "team": cached.team_name,
            "season": cached.season,
            "week": cached.week,
            "position": cached.position,
            "grade": cached.grade,
            "rank": cached.rank,
            "yards_per_target": cached.yards_per_target,
            "yards_per_rush": cached.yards_per_rush,
            "pressure_rate": cached.pressure_rate,
            "pass_td_rate": cached.pass_td_rate,
            "rush_td_rate": cached.rush_td_rate,
            "explosive_rate": cached.explosive_rate,
        }

    if defense:
        metrics = derive_from_defense(defense, position)
    else:
        metrics = {
            "grade": "C",
            "rank": 65,
            "yards_per_target": 7.8,
            "yards_per_rush": 4.3,
            "pressure_rate": 0.22,
            "pass_td_rate": 0.035,
            "rush_td_rate": 0.03,
            "explosive_rate": 0.1,
        }

    return {
        "team": team,
        "season": season,
        "week": week,
        "position": position,
        **metrics,
    }
