from __future__ import annotations

from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


def confidence_label(score: float | None) -> str:
    value = float(score if score is not None else 0.5)
    if value >= 0.75:
        return "High confidence"
    if value >= 0.5:
        return "Medium confidence"
    return "Limited data"


def uncertainty_labels(
    *,
    confidence_score: float | None,
    source_freshness: str | None,
    injury: Injury | None = None,
) -> list[str]:
    labels: list[str] = []
    if confidence_label(confidence_score) == "Limited data":
        labels.append("Limited data")
    if source_freshness in {"stale", "unknown"}:
        labels.append("Stale stat warning")
    if injury and injury.status and injury.status.upper() not in {"FULL", "ACTIVE", "PROBABLE"}:
        labels.append("Injury uncertainty")
    return labels


def calculate_projection_confidence(
    *,
    projection: WeeklyProjection,
    usage: UsageShare | None = None,
    team_environment: TeamEnvironment | None = None,
    injury: Injury | None = None,
    source_freshness: str | None = None,
) -> float:
    score = 0.45
    if usage is not None:
        score += 0.18
    if team_environment is not None:
        score += 0.14
    if source_freshness == "fresh":
        score += 0.12
    elif source_freshness == "stale":
        score -= 0.12
    spread = max(0.0, float(projection.ceiling or 0.0) - float(projection.floor or 0.0))
    points = max(1.0, float(projection.fantasy_points or 0.0))
    if spread / points <= 0.55:
        score += 0.08
    elif spread / points >= 1.2:
        score -= 0.1
    if injury and injury.status and injury.status.upper() not in {"FULL", "ACTIVE"}:
        score -= 0.15
    return round(max(0.05, min(0.95, score)), 3)


def generated_at_or_now(projection: WeeklyProjection) -> datetime:
    return projection.generated_at or projection.updated_at or datetime.now(timezone.utc)
