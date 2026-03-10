from __future__ import annotations

from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
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
