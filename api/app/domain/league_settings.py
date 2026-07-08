from __future__ import annotations

from copy import deepcopy

IMMUTABLE_ROSTER_KEYS = {"QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "BENCH", "IR", "BE"}


def league_settings_snapshot(settings_row) -> dict:
    return {
        "scoring_json": deepcopy(settings_row.scoring_json or {}),
        "roster_slots_json": deepcopy(settings_row.roster_slots_json or {}),
        "playoff_teams": settings_row.playoff_teams,
        "waiver_type": settings_row.waiver_type,
        "trade_review_type": settings_row.trade_review_type,
        "superflex_enabled": settings_row.superflex_enabled,
        "kicker_enabled": settings_row.kicker_enabled,
        "defense_enabled": settings_row.defense_enabled,
    }


def payload_settings_snapshot(payload_settings) -> dict:
    return {
        "scoring_json": deepcopy(payload_settings.scoring_json or {}),
        "roster_slots_json": deepcopy(payload_settings.roster_slots_json or {}),
        "playoff_teams": payload_settings.playoff_teams,
        "waiver_type": payload_settings.waiver_type,
        "trade_review_type": payload_settings.trade_review_type,
        "superflex_enabled": payload_settings.superflex_enabled,
        "kicker_enabled": payload_settings.kicker_enabled,
        "defense_enabled": payload_settings.defense_enabled,
    }


def roster_settings_changed(before: dict, after: dict) -> bool:
    return before.get("roster_slots_json") != after.get("roster_slots_json")


def scoring_settings_changed(before: dict, after: dict) -> bool:
    return before.get("scoring_json") != after.get("scoring_json")
