from __future__ import annotations

from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.scoring_service import calculate_player_fantasy_points


def projection_to_normalized_stats(projection: WeeklyProjection) -> dict[str, float]:
    return {
        "pass_yards": projection.pass_yards or 0.0,
        "pass_tds": projection.pass_tds or 0.0,
        "interceptions": projection.interceptions or 0.0,
        "rush_yards": projection.rush_yards or 0.0,
        "rush_tds": projection.rush_tds or 0.0,
        "receptions": projection.receptions or 0.0,
        "rec_yards": projection.rec_yards or 0.0,
        "rec_tds": projection.rec_tds or 0.0,
        "fumbles_lost": 0.0,
        "fg_made_0_39": 0.0,
        "fg_made_40_49": 0.0,
        "fg_made_50_plus": 0.0,
        "xp_made": 0.0,
    }


def calculate_league_projection_points(
    projection: WeeklyProjection,
    scoring_json: dict,
) -> tuple[float, dict]:
    stats = projection_to_normalized_stats(projection)
    return calculate_player_fantasy_points(stats, scoring_json)


def calculate_league_projection_range(
    projection: WeeklyProjection,
    scoring_json: dict,
) -> tuple[float | None, float | None]:
    league_points, _ = calculate_league_projection_points(projection, scoring_json)
    if not projection.fantasy_points:
        return None, None

    floor_ratio = max(0.0, (projection.floor or 0.0) / projection.fantasy_points)
    ceiling_ratio = max(floor_ratio, (projection.ceiling or 0.0) / projection.fantasy_points)
    return round(league_points * floor_ratio, 2), round(league_points * ceiling_ratio, 2)
