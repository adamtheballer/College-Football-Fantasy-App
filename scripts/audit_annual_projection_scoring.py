#!/usr/bin/env python3
"""Reconcile annual Sheet totals with the app's canonical scoring contract.

This is a release gate only.  It never writes a database row and never treats
the workbook's ``FANTASY PROJ.`` column as a weekly projection input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points


SOURCE_COLUMNS = {
    "pass_yards": "PASS YDS",
    "pass_tds": "PASS TDS",
    "interceptions": "INTS",
    "rush_yards": "RUSH YDS",
    "rush_tds": "RUSH TDS",
    "receptions": "RECEPTIONS",
    "rec_yards": "REC YDS",
    "rec_tds": "REC TDS",
    "xp_made": "XP",
}


def _number(value: str | None) -> float | None:
    try:
        return float((value or "").replace(",", ""))
    except ValueError:
        return None


def _component_state(value: str | None) -> str:
    """Return missing/invalid/valid without ever turning blanks into zero."""
    text = (value or "").strip()
    if not text:
        return "missing"
    return "valid" if _number(text) is not None else "invalid"


def _position(row: dict[str, str]) -> str:
    return (row.get("POSITION") or "").strip().upper()[:2]


def _canonical_stats(row: dict[str, str]) -> dict[str, str | None]:
    return {stat: row.get(column) for stat, column in SOURCE_COLUMNS.items()}


def canonical_projection_points(row: dict[str, str]) -> float | None:
    """Return a component-derived annual total when the source can prove one.

    ``FANTASY PROJ.`` is retained as a source-provided comparison value only.
    It is not an input to the app's standard-scoring total.  In particular, a
    kicker total-FG value cannot be translated into the app's distance-tiered
    kicker scoring without inventing a distance distribution.
    """

    position = _position(row)
    if not position:
        return None
    required_columns = tuple(SOURCE_COLUMNS.values())
    if any(_component_state(row.get(column)) != "valid" for column in required_columns):
        return None
    if position == "K" and _number(row.get("FG")) not in (None, 0.0):
        return None
    points, _ = calculate_player_fantasy_points(_canonical_stats(row), {}, position)
    return points


def audit(rows: list[dict[str, str]]) -> dict[str, Any]:
    outcomes: Counter[str] = Counter()
    outcome_by_position: Counter[str] = Counter()
    findings: list[dict[str, Any]] = []
    max_difference = 0.0
    for row_number, row in enumerate(rows, start=2):
        position = _position(row)
        identity = {
            "player": (row.get("PLAYER") or "").strip() or None,
            "team": (row.get("TEAM") or "").strip() or None,
            "position": position or None,
        }
        sheet_points = _number(row.get("FANTASY PROJ."))
        required_columns = tuple(SOURCE_COLUMNS.values())
        missing_components = [column for column in required_columns if _component_state(row.get(column)) == "missing"]
        invalid_components = [column for column in required_columns if _component_state(row.get(column)) == "invalid"]
        if not identity["player"] or not identity["team"] or not identity["position"]:
            outcome = "UNMATCHED_PLAYER"
            canonical_points = None
            difference = None
            reason = "canonical_identity_fields_are_incomplete"
        elif invalid_components:
            outcome = "INVALID_COMPONENT"
            canonical_points = None
            difference = None
            reason = "one_or_more_canonical_component_columns_are_invalid"
        elif missing_components:
            outcome = "MISSING_COMPONENT"
            canonical_points = None
            difference = None
            reason = "one_or_more_canonical_component_columns_are_blank"
        elif position == "K" and _number(row.get("FG")) not in (None, 0.0):
            # The canonical kicker model requires distance buckets.  A total
            # FG count cannot safely be allocated across them.
            outcome = "UNSCORABLE_KICKER_DISTANCE"
            canonical_points = None
            difference = None
            reason = "annual_sheet_has_total_field_goals_without_distance_buckets"
        elif sheet_points is None:
            outcome = "MISSING_SHEET_TOTAL"
            canonical_points = canonical_projection_points(row)
            difference = None
            reason = "FANTASY_PROJ_blank"
        else:
            canonical_points = canonical_projection_points(row)
            difference = round(canonical_points - sheet_points, 2)
            if abs(difference) < 0.005:
                outcome = "EXACT_MATCH"
                reason = "canonical_scoring_matches_sheet_total"
            else:
                outcome = "MISMATCH"
                reason = "unproven_scoring_rule_difference"
                max_difference = max(max_difference, abs(difference))
        outcomes[outcome] += 1
        outcome_by_position[f"{position}:{outcome}"] += 1
        if outcome != "EXACT_MATCH":
            findings.append({
                "row_number": row_number,
                "source_row": row_number,
                "canonical_player_identity": identity,
                "player": identity["player"],
                "team": identity["team"],
                "position": position,
                "sheet_fantasy_points": sheet_points,
                "canonical_fantasy_points": canonical_points,
                "difference_canonical_minus_sheet": difference,
                "absolute_delta": abs(difference) if difference is not None else None,
                "reason": reason,
            })
    return {
        "policy_name": "component_stats_canonical_scoring_v1",
        "source_rows": len(rows),
        "canonical_scoring_profile": "app_default_rules",
        "outcome_counts": dict(sorted(outcomes.items())),
        "outcome_counts_by_position": dict(sorted(outcome_by_position.items())),
        "exact_matches": outcomes["EXACT_MATCH"],
        "mismatches": outcomes["MISMATCH"],
        "maximum_absolute_difference": max_difference,
        "review_required": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("reports/source-imports/2026/player-projections.csv"))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8") as handle:
        report = audit(list(csv.DictReader(handle)))
    report["source_sha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("source_rows", "exact_matches", "mismatches", "maximum_absolute_difference")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
