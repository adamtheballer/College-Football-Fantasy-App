import math


def _valid_projection(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        projection = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(projection) or projection < 0:
        return None
    return projection


def calculate_matchup_win_probability(
    my_projected_points: float | None,
    opponent_projected_points: float | None,
) -> tuple[float, float] | None:
    """Return deterministic projected win chances from weekly lineup totals.

    The API intentionally returns full precision. Presentation layers round one
    side and derive the other complement so the displayed values always total
    exactly 100.0%. A missing or invalid total is not a 50/50 matchup.
    """

    my_total = _valid_projection(my_projected_points)
    opponent_total = _valid_projection(opponent_projected_points)
    if my_total is None or opponent_total is None:
        return None

    margin = abs(my_total - opponent_total)
    advantage = margin / 2.0 if margin <= 10.0 else 5.0 * (margin / 10.0) ** 2
    advantage = min(advantage, 45.0)
    favorite_probability = 50.0 + advantage
    underdog_probability = 50.0 - advantage

    if my_total == opponent_total:
        return 50.0, 50.0
    if my_total > opponent_total:
        return favorite_probability, underdog_probability
    return underdog_probability, favorite_probability
