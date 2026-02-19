from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

ProjectionInput = Mapping[str, Any]


@dataclass(frozen=True)
class ScoringRules:
    passing_yards: float = 1 / 25
    passing_tds: float = 4.0
    interceptions: float = -2.0
    rushing_yards: float = 1 / 10
    rushing_tds: float = 6.0
    receiving_yards: float = 1 / 10
    receiving_tds: float = 6.0
    receptions: float = 0.0
    fumbles_lost: float = -2.0


DEFAULT_STANDARD_RULES = ScoringRules()
HALF_PPR_RULES = ScoringRules(receptions=0.5)
PPR_RULES = ScoringRules(receptions=1.0)

SCORING_PRESETS: dict[str, ScoringRules] = {
    "standard": DEFAULT_STANDARD_RULES,
    "half_ppr": HALF_PPR_RULES,
    "ppr": PPR_RULES,
}

PROJECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "passing_yards": ("passing_yards", "pass_yards", "pass_yds"),
    "passing_tds": ("passing_tds", "pass_tds", "pass_td"),
    "interceptions": ("interceptions", "ints", "pass_ints"),
    "rushing_yards": ("rushing_yards", "rush_yards", "rush_yds"),
    "rushing_tds": ("rushing_tds", "rush_tds", "rush_td"),
    "receiving_yards": ("receiving_yards", "rec_yards", "rec_yds"),
    "receiving_tds": ("receiving_tds", "rec_tds", "rec_td"),
    "receptions": ("receptions", "rec", "recs"),
    "fumbles_lost": ("fumbles_lost", "fumbles"),
}

NON_NEGATIVE_FIELDS = {
    "passing_tds",
    "interceptions",
    "rushing_tds",
    "receiving_tds",
    "receptions",
    "fumbles_lost",
}


def _extract_value(projection: ProjectionInput, aliases: tuple[str, ...]) -> Any:
    for key in aliases:
        if key in projection:
            return projection[key]
    return 0.0


def _coerce_number(value: Any, field: str, *, strict: bool) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        if strict:
            raise ValueError(f"{field} must be numeric, got bool")
        return 0.0
    if isinstance(value, str) and not value.strip():
        return 0.0
    if isinstance(value, (int, float, str)):
        try:
            number = float(value)
        except (TypeError, ValueError):
            if strict:
                raise ValueError(f"{field} must be numeric")
            return 0.0
    else:
        if strict:
            raise ValueError(f"{field} must be numeric")
        return 0.0
    if not isfinite(number):
        if strict:
            raise ValueError(f"{field} must be finite")
        return 0.0
    if field in NON_NEGATIVE_FIELDS and number < 0:
        if strict:
            raise ValueError(f"{field} must be non-negative")
        return 0.0
    return number


def normalize_projection(
    projection: ProjectionInput,
    *,
    strict: bool = True,
    aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> dict[str, float]:
    alias_map = aliases or PROJECTION_ALIASES
    normalized: dict[str, float] = {}
    for field, field_aliases in alias_map.items():
        raw_value = _extract_value(projection, field_aliases)
        normalized[field] = _coerce_number(raw_value, field, strict=strict)
    return normalized


class ProjectionScorer:
    def __init__(
        self,
        rules: ScoringRules | None = None,
        *,
        strict: bool = True,
        round_points: int | None = 2,
        aliases: Mapping[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.rules = rules or DEFAULT_STANDARD_RULES
        self.strict = strict
        self.round_points = round_points
        self.aliases = aliases or PROJECTION_ALIASES

    def score(self, projection: ProjectionInput) -> float:
        stats = normalize_projection(projection, strict=self.strict, aliases=self.aliases)
        total = (
            stats["passing_yards"] * self.rules.passing_yards
            + stats["passing_tds"] * self.rules.passing_tds
            + stats["interceptions"] * self.rules.interceptions
            + stats["rushing_yards"] * self.rules.rushing_yards
            + stats["rushing_tds"] * self.rules.rushing_tds
            + stats["receiving_yards"] * self.rules.receiving_yards
            + stats["receiving_tds"] * self.rules.receiving_tds
            + stats["receptions"] * self.rules.receptions
            + stats["fumbles_lost"] * self.rules.fumbles_lost
        )
        if self.round_points is None:
            return total
        return round(total, self.round_points)


def score_projection(
    projection: ProjectionInput,
    rules: ScoringRules | None = None,
    *,
    strict: bool = True,
    round_points: int | None = 2,
    aliases: Mapping[str, tuple[str, ...]] | None = None,
) -> float:
    return ProjectionScorer(
        rules=rules,
        strict=strict,
        round_points=round_points,
        aliases=aliases,
    ).score(projection)


def resolve_scoring_rules(scoring_type: str | None, rules: ScoringRules | None = None) -> ScoringRules:
    if rules is not None:
        return rules
    if not scoring_type:
        return DEFAULT_STANDARD_RULES
    key = scoring_type.strip().lower()
    if key not in SCORING_PRESETS:
        raise ValueError(f"Unknown scoring type: {scoring_type}")
    return SCORING_PRESETS[key]
