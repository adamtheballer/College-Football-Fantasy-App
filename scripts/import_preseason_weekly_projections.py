#!/usr/bin/env python3
"""Build transparent, unpublished PRESEASON_WEEKLY_V1 rows from sealed sources.

This never calls the generic projection engine and performs no network I/O.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from sqlalchemy import select

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from collegefootballfantasy_api.app.domain.scoring_rules import BETA_KICKER_RULES
from collegefootballfantasy_api.app.models.college_team import CollegeTeam
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.team_schedule_import import parse_schedule_csv
from scripts.audit_preseason_source_contract import _key, _position, _team
from scripts.freeze_authoritative_sheet_snapshots import REQUIRED_WORKBOOKS

MODEL_VERSION = "preseason_weekly_v1"
POLICY_NAME = "component_stats_canonical_scoring_v2_beta_flat_kicker"
COMPONENTS = {
    "pass_attempts": "ATTEMPTS", "receptions": "RECEPTIONS", "pass_yards": "PASS YDS", "pass_tds": "PASS TDS",
    "interceptions": "INTS", "rush_yards": "RUSH YDS", "rush_tds": "RUSH TDS", "rec_yards": "REC YDS",
    "rec_tds": "REC TDS", "field_goals_made_0_to_39": "FG", "extra_points_made": "XP",
}


def _number(value: str | None) -> float | None:
    try:
        return float((value or "").replace(",", ""))
    except ValueError:
        return None


def _source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sealed_annual_baseline_source(source_hash: str) -> str:
    """Return the exact provenance marker stored on PRESEASON weekly rows.

    Weekly rows are derived from the sealed annual-projection workbook, not
    the umbrella six-workbook manifest.  Publishing must compare the same
    immutable annual-source hash the importer stored, otherwise verified rows
    can never become visible on player cards.
    """

    normalized = source_hash.strip().lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise ValueError("Annual projection source hash must be a SHA-256 digest.")
    return f"sealed:{normalized[:12]}"


def _canonical_source_team(value: str | None) -> str:
    """Use the same reviewed-team normalization as the source contract.

    Notre Dame is intentionally eligible but is not a Power Four conference
    member, so calling the Power Four resolver directly turns its uppercase
    XLSX value into a different key than the schedule workbook's team name.
    """

    return _team(value) or (value or "").strip()


def _require_inputs(manifest_path: Path, annual_path: Path, schedule_path: Path, audit_path: Path) -> tuple[str, dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshots = manifest.get("snapshots") if isinstance(manifest, dict) else None
    if not isinstance(snapshots, list) or {item.get("workbook") for item in snapshots if isinstance(item, dict)} != REQUIRED_WORKBOOKS:
        raise ValueError("A sealed six-workbook source manifest is required.")
    hashes = {item.get("sha256") for item in snapshots if isinstance(item, dict)}
    if _source_hash(annual_path) not in hashes or _source_hash(schedule_path) not in hashes:
        raise ValueError("Annual projection and schedule inputs must both be listed in the sealed manifest.")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("policy_name") != POLICY_NAME or audit.get("source_sha256") != _source_hash(annual_path):
        raise ValueError("Scoring reconciliation source hash or canonical policy does not match the sealed annual snapshot.")
    return _source_hash(annual_path), audit


def _stats(row: dict[str, str], games: int) -> dict[str, float] | None:
    values = {target: _number(row.get(source)) for target, source in COMPONENTS.items()}
    if any(value is None for value in values.values()):
        return None
    return {key: value / games for key, value in values.items() if value is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annual", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--sealed-manifest", type=Path, required=True)
    parser.add_argument("--scoring-report", type=Path, required=True)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    annual_hash, _audit = _require_inputs(args.sealed_manifest, args.annual, args.schedule, args.scoring_report)
    with args.annual.open(newline="", encoding="utf-8") as handle:
        annual_rows = list(csv.DictReader(handle))
    schedule_rows, schedule_report = parse_schedule_csv(args.schedule.read_text(encoding="utf-8-sig"), season=args.season)
    if schedule_report.has_errors:
        raise SystemExit("Sealed schedule snapshot has validation errors; weekly projections were not generated.")
    schedules = {(_canonical_source_team(row.team_name), row.week): row for row in schedule_rows}
    game_counts = Counter(_canonical_source_team(row.team_name) for row in schedule_rows if not row.is_bye)
    ensure_models_registered()
    report = {"mode": "apply" if args.apply else "dry-run", "model_version": MODEL_VERSION, "source_sha256": annual_hash, "counts": Counter(), "rows": []}
    with SessionLocal() as db:
        players = db.scalars(select(Player)).all()
        teams = db.scalars(select(CollegeTeam)).all()
        player_by_key = {_key(player.name, _canonical_source_team(player.school), _position(player.position)): player for player in players}
        team_by_name = {_canonical_source_team(team.name): team for team in teams}
        try:
            for annual in annual_rows:
                source_key = _key(annual.get("PLAYER"), _canonical_source_team(annual.get("TEAM")), _position(annual.get("POSITION")))
                player = player_by_key.get(source_key)
                if player is None:
                    report["counts"]["unmatched"] += 1; report["rows"].append({"player": annual.get("PLAYER"), "status": "UNMATCHED_IDENTITY"}); continue
                team_name = _canonical_source_team(player.school)
                canonical_team = team_by_name.get(team_name)
                if canonical_team is None:
                    report["counts"]["missing_team"] += 1
                    report["rows"].append({"player_id": player.id, "status": "MISSING_CANONICAL_TEAM"})
                    continue
                games = game_counts.get(team_name, 0)
                if not games:
                    report["counts"]["missing_schedule"] += 1; continue
                weekly = _stats(annual, games)
                status = "ACTIVE" if weekly is not None else "MISSING_BASELINE"
                for week in range(1, 14):
                    schedule = schedules.get((team_name, week))
                    if schedule is None:
                        report["counts"]["missing_schedule"] += 1; continue
                    opponent_team = team_by_name.get(_canonical_source_team(schedule.opponent_name)) if schedule.opponent_name else None
                    row_status = "BYE" if schedule.is_bye else status
                    if not schedule.is_bye and opponent_team is None:
                        row_status = "MISSING_OPPONENT"
                    points = 0.0 if row_status == "BYE" else None
                    if row_status == "ACTIVE" and weekly is not None:
                        points, _ = calculate_player_fantasy_points({"pass_yards": weekly["pass_yards"], "pass_tds": weekly["pass_tds"], "interceptions": weekly["interceptions"], "rush_yards": weekly["rush_yards"], "rush_tds": weekly["rush_tds"], "receptions": weekly["receptions"], "rec_yards": weekly["rec_yards"], "rec_tds": weekly["rec_tds"], "fg_made_0_30": weekly["field_goals_made_0_to_39"], "xp_made": weekly["extra_points_made"]}, BETA_KICKER_RULES if player.position == "K" else {}, player.position)
                    report["counts"][row_status.lower()] += 1
                    if not args.apply:
                        continue
                    existing = db.scalar(select(WeeklyProjection).where(WeeklyProjection.player_id == player.id, WeeklyProjection.season == args.season, WeeklyProjection.week == week, WeeklyProjection.projection_version == "PRESEASON"))
                    baseline_source = sealed_annual_baseline_source(annual_hash)
                    if existing and existing.baseline_source != baseline_source:
                        raise ValueError(f"Refusing to overwrite a different sealed PRESEASON source for player {player.id} week {week}.")
                    values = dict(player_id=player.id, season=args.season, week=week, projection_version="PRESEASON", is_published=False, model_version=MODEL_VERSION, baseline_source=baseline_source, team_id=canonical_team.id, opponent_team_id=opponent_team.id if opponent_team else None, projection_status=row_status, baseline_games_played=games, neutral_baseline=points or 0.0, fantasy_points=points or 0.0, floor=points or 0.0, ceiling=points or 0.0, boom_prob=0.0, bust_prob=0.0, availability_multiplier=1.0, usage_multiplier=1.0, offense_multiplier=1.0, opponent_defense_multiplier=1.0, confidence=1.0 if row_status == "ACTIVE" else 0.0, fallback_reason=None if row_status == "ACTIVE" else row_status)
                    if weekly:
                        values.update(weekly)
                    if existing:
                        for key, value in values.items(): setattr(existing, key, value)
                        report["counts"]["updated"] += 1
                    else:
                        db.add(WeeklyProjection(**values)); report["counts"]["inserted"] += 1
            if args.apply: db.commit()
            else: db.rollback()
        except Exception:
            db.rollback(); raise
    report["counts"] = dict(report["counts"])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"mode": report["mode"], "counts": report["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
