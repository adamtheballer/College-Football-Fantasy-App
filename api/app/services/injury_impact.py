from __future__ import annotations


def injury_projection_multiplier(normalized_status: str | None) -> float:
    status = (normalized_status or "unknown").lower()
    if status == "healthy":
        return 1.0
    if status == "questionable":
        return 0.7
    if status == "doubtful":
        return 0.25
    if status == "out":
        return 0.0
    if status == "season_out":
        return 0.0
    return 0.85


def injury_projection_delta(base_projection: float | None, normalized_status: str | None) -> tuple[float, float, float, str]:
    base = float(base_projection or 0.0)
    multiplier = injury_projection_multiplier(normalized_status)
    delta = round((base * multiplier) - base, 2)
    confidence = 0.9 if normalized_status in {"out", "season_out", "healthy"} else 0.65
    reason = f"Injury status {normalized_status or 'unknown'} applies a {multiplier:.2f} projection multiplier."
    return delta, multiplier, confidence, reason
