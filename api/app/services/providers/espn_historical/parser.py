from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .mappings import CATEGORY_ALIASES, INDEX_FALLBACKS, LABEL_ALIASES
from .schemas import ProviderPlayerHistory, ProviderPlayerSeason, SOURCE_REVISION

MISSING_NUMERIC_VALUES = {"", "-", "—", "--", "N/A", "NA", None}


class ESPNHistoricalStatsParseError(ValueError):
    pass


def parse_number(value: Any) -> tuple[float | None, str | None]:
    if value in MISSING_NUMERIC_VALUES:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    text = str(value).strip()
    if text in MISSING_NUMERIC_VALUES:
        return None, None
    if "/" in text and re.fullmatch(r"\d+(\.\d+)?/\d+(\.\d+)?", text):
        first, _second = text.split("/", 1)
        return float(first), f"combined numeric value '{text}' parsed as first component"
    cleaned = text.replace(",", "").replace("%", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return float(cleaned), None
    return None, f"could not parse numeric value '{text}'"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _category_key(display_name: str | None) -> str | None:
    normalized = (display_name or "").strip().lower()
    return CATEGORY_ALIASES.get(normalized)


def _extract_labels(category: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for key in ("labels", "names", "displayNames", "statLabels"):
        raw = category.get(key)
        if isinstance(raw, list):
            labels = [str(item).strip() for item in raw]
            break
    return labels


def _extract_player_name(payload: dict[str, Any]) -> str | None:
    athlete = payload.get("athlete") if isinstance(payload.get("athlete"), dict) else {}
    return _text(athlete.get("displayName") or athlete.get("fullName") or athlete.get("name"))


def _extract_position(payload: dict[str, Any]) -> str | None:
    athlete = payload.get("athlete") if isinstance(payload.get("athlete"), dict) else {}
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    return _text(position.get("abbreviation") or position.get("displayName"))


def _extract_team_name(stat_year: dict[str, Any]) -> str | None:
    team = stat_year.get("team") if isinstance(stat_year.get("team"), dict) else {}
    return _text(team.get("displayName") or team.get("shortDisplayName") or stat_year.get("teamSlug"))


def _season_year(stat_year: dict[str, Any]) -> int | None:
    season = stat_year.get("season") if isinstance(stat_year.get("season"), dict) else {}
    value = season.get("year") or stat_year.get("season") or stat_year.get("year")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_player_history(payload: dict[str, Any], provider_player_id: str, fetched_at: datetime | None = None, source_url: str | None = None) -> ProviderPlayerHistory:
    if not isinstance(payload, dict):
        raise ESPNHistoricalStatsParseError("ESPN historical stats payload must be an object")
    categories = payload.get("categories")
    if not isinstance(categories, list):
        raise ESPNHistoricalStatsParseError("ESPN historical stats payload is missing categories")

    fetched_at = fetched_at or datetime.now(timezone.utc)
    position = _extract_position(payload)
    seasons: dict[int, ProviderPlayerSeason] = {}
    warnings: list[str] = []

    for category in categories:
        if not isinstance(category, dict):
            continue
        category_key = _category_key(_text(category.get("displayName") or category.get("name")))
        if not category_key:
            continue
        labels = _extract_labels(category)
        statistics = category.get("statistics")
        if not isinstance(statistics, list):
            continue
        for stat_year in statistics:
            if not isinstance(stat_year, dict):
                continue
            year = _season_year(stat_year)
            if not year:
                warnings.append(f"skipped {category_key} row without season year")
                continue
            season = seasons.setdefault(
                year,
                ProviderPlayerSeason(
                    season=year,
                    team_provider_id=_text(stat_year.get("teamId")),
                    team_name=_extract_team_name(stat_year),
                    position=position,
                    source_url=source_url,
                ),
            )
            stats = stat_year.get("stats")
            if not isinstance(stats, list):
                continue
            season.categories.setdefault(category_key, {})
            season.raw_labels.setdefault(category_key, {})
            season.unknown_labels.setdefault(category_key, {})
            for index, raw_value in enumerate(stats):
                raw_label = labels[index] if index < len(labels) else str(index)
                normalized_label = raw_label.upper().replace(" ", "")
                canonical_key = LABEL_ALIASES.get(category_key, {}).get(normalized_label)
                if not canonical_key:
                    canonical_key = INDEX_FALLBACKS.get(category_key, {}).get(index)
                parsed, warning = parse_number(raw_value)
                if warning:
                    season.warnings.append(warning)
                season.raw_labels[category_key][raw_label] = raw_value
                if not canonical_key:
                    season.unknown_labels[category_key][raw_label] = raw_value
                    continue
                if canonical_key == "games_played":
                    season.games_played = int(parsed) if parsed is not None else None
                    continue
                if canonical_key == "games_started":
                    season.games_started = int(parsed) if parsed is not None else None
                    continue
                season.categories[category_key][canonical_key] = parsed

    return ProviderPlayerHistory(
        provider="espn",
        provider_player_id=str(provider_player_id),
        player_name=_extract_player_name(payload),
        fetched_at=fetched_at,
        source_revision=SOURCE_REVISION,
        seasons=sorted(seasons.values(), key=lambda row: row.season, reverse=True),
        raw_payload=payload,
        warnings=warnings,
    )
