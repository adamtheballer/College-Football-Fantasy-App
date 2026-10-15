"""Shared projection scoring for selected league/standard contexts."""
from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection

def is_standard_scoring(scoring_rules: dict | None, position: str) -> bool:
    if scoring_rules is None:
        return True
    from collegefootballfantasy_api.app.domain.scoring_rules import validate_scoring_rules
    from collegefootballfantasy_api.app.scoring import get_scoring_rules
    return validate_scoring_rules(scoring_rules).for_position(position)==validate_scoring_rules(get_scoring_rules()).for_position(position)

def projection_stats(row: WeeklyProjection) -> dict[str, float]:
    # Published projection sources provide 0--39, 40--49, and 50+ volume,
    # rather than exact made-kick distances.  Split that expected volume into
    # the fixed league scoring tiers so a league's field-goal settings still
    # apply to projections; live ESPN box scores use exact distances.
    short_field_goals = float(row.field_goals_made_0_to_39 or row.field_goals_made_0_to_49 or 0.0)
    medium_field_goals = float(row.field_goals_made_40_to_49 or 0.0)
    long_field_goals = float(row.field_goals_made_50_plus or 0.0)
    return {
        "pass_yards": float(row.pass_yards or 0.0),
        "pass_tds": float(row.pass_tds or 0.0),
        "interceptions": float(row.interceptions or 0.0),
        "rush_yards": float(row.rush_yards or 0.0),
        "rush_tds": float(row.rush_tds or 0.0),
        "receptions": float(row.receptions or 0.0),
        "rec_yards": float(row.rec_yards or 0.0),
        "rec_tds": float(row.rec_tds or 0.0),
        "fg_made_0_30": short_field_goals * 0.75,
        "fg_made_31_40": short_field_goals * 0.25,
        "fg_made_41_50": medium_field_goals,
        "fg_made_51_60": long_field_goals,
        "fg_made_61_plus": 0.0,
        "xp_made": float(row.extra_points_made or 0.0),
    }


def points_for_projection(player: Player, row: WeeklyProjection, scoring_rules: dict | None) -> float | None:
    return points_for_projection_inputs(position=player.position, standard_points=row.fantasy_points, stats=projection_stats(row), scoring_rules=scoring_rules)


def points_for_projection_inputs(*, position: str, standard_points: float | None, stats: dict, scoring_rules: dict | None) -> float | None:
    # A published weekly snapshot's fantasy-points field is already its
    # standard scoring result. Rescore raw categories for a selected league.
    if is_standard_scoring(scoring_rules,position) and standard_points is not None:
        return float(standard_points)
    if not any(stats.values()):
        return 0.0 if standard_points == 0 else None
    points, _ = calculate_player_fantasy_points(stats, scoring_rules, position)
    return points
