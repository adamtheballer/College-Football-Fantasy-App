import math

NON_STARTER_SLOTS = {"BENCH", "IR"}


def is_starting_slot(slot: str | None) -> bool:
    return bool(slot) and slot.upper() not in NON_STARTER_SLOTS


def estimate_player_std_dev(
    fantasy_points: float,
    floor: float | None = None,
    ceiling: float | None = None,
) -> float:
    projection = max(float(fantasy_points or 0.0), 0.0)
    if ceiling is not None and floor is not None and ceiling > floor:
        return max((float(ceiling) - float(floor)) / 3.92, 2.5)
    return max(projection * 0.35, 2.5)


def normal_cdf(z_score: float) -> float:
    return 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))


def calculate_matchup_win_probability(
    my_projected_points: float,
    opponent_projected_points: float,
    my_variance: float,
    opponent_variance: float,
) -> tuple[float, float]:
    mean_diff = float(my_projected_points or 0.0) - float(opponent_projected_points or 0.0)
    std_dev = math.sqrt(max(float(my_variance or 0.0) + float(opponent_variance or 0.0), 1.0))
    my_probability = normal_cdf(mean_diff / std_dev) * 100.0
    my_probability = round(min(99.0, max(1.0, my_probability)), 1)
    opponent_probability = round(100.0 - my_probability, 1)
    return my_probability, opponent_probability
