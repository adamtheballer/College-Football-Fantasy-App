from __future__ import annotations

from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.projections.confidence import confidence_label, uncertainty_labels
from collegefootballfantasy_api.app.services.matchup_grades import build_matchup_row


def build_projection_reasons(
    player_name: str,
    team: str,
    position: str,
    season: int,
    week: int,
    team_env: TeamEnvironment | None,
    usage: UsageShare | None,
    injury: Injury | None,
    defense: DefenseRating | None,
) -> list[dict]:
    reasons: list[dict] = []
    matchup = build_matchup_row(team, season, week, position, defense, None)
    grade = matchup["grade"]
    if grade in {"A+", "A"}:
        reasons.append({"type": "matchup", "detail": f"Favorable matchup (defense rank {matchup['rank']})"})
    elif grade in {"D", "F"}:
        reasons.append({"type": "matchup", "detail": f"Difficult matchup (defense rank {matchup['rank']})"})
    else:
        reasons.append({"type": "matchup", "detail": f"Neutral matchup (defense rank {matchup['rank']})"})

    if usage:
        if usage.target_share >= 0.2 or usage.rush_share >= 0.2:
            reasons.append({"type": "usage", "detail": "High usage share projected"})
        elif usage.target_share >= 0.12 or usage.rush_share >= 0.12:
            reasons.append({"type": "usage", "detail": "Stable role and usage share"})

    if team_env:
        if team_env.expected_plays >= 70:
            reasons.append({"type": "environment", "detail": "High team tempo expected"})
        elif team_env.expected_points >= 30:
            reasons.append({"type": "environment", "detail": "Strong scoring environment"})

    if injury and injury.status and injury.status.upper() != "FULL":
        reasons.append({"type": "injury", "detail": f"Injury status: {injury.status}"})

    deduped: list[dict] = []
    seen = set()
    for reason in reasons:
        if reason["detail"] not in seen:
            deduped.append(reason)
            seen.add(reason["detail"])
    return deduped[:3]


def build_projection_explanation_contract(
    *,
    projection: WeeklyProjection,
    player_name: str,
    team: str,
    position: str,
    team_env: TeamEnvironment | None,
    usage: UsageShare | None,
    injury: Injury | None,
    defense: DefenseRating | None,
) -> dict:
    matchup = build_matchup_row(team, projection.season, projection.week, position, defense, None)
    baseline = {
        "fantasy_points": projection.fantasy_points,
        "expected_plays": projection.expected_plays,
        "source": "weekly_projection",
    }
    opponent_adjustment = {
        "grade": matchup["grade"],
        "rank": matchup["rank"],
        "detail": f"Opponent matchup grade {matchup['grade']}",
    }
    injury_adjustment = {
        "status": injury.status if injury else "FULL",
        "detail": f"Injury status: {injury.status}" if injury and injury.status else "No injury designation",
    }
    usage_adjustment = {
        "rush_share": usage.rush_share if usage else None,
        "target_share": usage.target_share if usage else None,
        "detail": "Usage share available" if usage else "Usage data unavailable",
    }
    environment_adjustment = {
        "expected_plays": team_env.expected_plays if team_env else None,
        "expected_points": team_env.expected_points if team_env else None,
        "detail": "Game environment available" if team_env else "Game environment unavailable",
    }
    return {
        "player": {"name": player_name, "team": team, "position": position},
        "baseline": baseline,
        "opponent_adjustment": opponent_adjustment,
        "injury_adjustment": injury_adjustment,
        "usage_adjustment": usage_adjustment,
        "weather_game_environment": environment_adjustment,
        "final_projection": {
            "fantasy_points": projection.fantasy_points,
            "floor": projection.floor,
            "ceiling": projection.ceiling,
            "boom_prob": projection.boom_prob,
            "bust_prob": projection.bust_prob,
        },
        "confidence": {
            "score": projection.confidence_score,
            "label": confidence_label(projection.confidence_score),
            "uncertainty_labels": uncertainty_labels(
                confidence_score=projection.confidence_score,
                source_freshness=projection.source_freshness,
                injury=injury,
            ),
        },
    }
