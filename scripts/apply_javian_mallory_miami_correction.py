#!/usr/bin/env python3
"""Apply the reviewed Javian Mallory Miami RB3 correction.

Default mode validates ESPN's exact profile and final Week 2 box score, then
rolls back.  ``--apply`` writes the idempotent correction and recalculates only
the completed Week 2 fantasy scoring affected by the new verified player row.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.services.javian_mallory_correction import (
    JAVIAN_MALLORY_ESPN_ID,
    MIAMI_ESPN_TEAM_ID,
    apply_javian_mallory_miami_correction,
)
from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--end-week", type=int, default=13)
    parser.add_argument("--apply", action="store_true", help="Persist after exact ESPN validation.")
    return parser.parse_args()


def _enrich_profile_from_current_roster(profile: dict, roster_payload: dict) -> dict:
    """Fill public profile gaps only from the same ESPN roster identity."""
    enriched = deepcopy(profile)
    athlete = enriched.get("athlete") if isinstance(enriched.get("athlete"), dict) else None
    groups = roster_payload.get("athletes") if isinstance(roster_payload, dict) else None
    roster_rows = [
        item
        for group in (groups or [])
        if isinstance(group, dict)
        for item in (group.get("items") or [])
        if isinstance(item, dict) and str(item.get("id") or "") == JAVIAN_MALLORY_ESPN_ID
    ]
    if athlete is None or len(roster_rows) != 1:
        return enriched
    for field in ("birthPlace", "headshot", "displayHeight", "displayWeight", "jersey"):
        if roster_rows[0].get(field) is not None:
            athlete[field] = roster_rows[0][field]
    return enriched


def main() -> int:
    args = parse_args()
    if not 2 <= args.end_week <= 13:
        raise ValueError("--end-week must be between 2 and 13.")
    ensure_models_registered()
    with ESPNClient() as espn:
        profile = espn.get_athlete_profile(JAVIAN_MALLORY_ESPN_ID)
        profile = _enrich_profile_from_current_roster(profile, espn.get_team_roster(MIAMI_ESPN_TEAM_ID))
        summary = espn.get_summary("401858213")

    with SessionLocal() as db:
        report = apply_javian_mallory_miami_correction(
            db,
            season=args.season,
            role_weeks=range(2, args.end_week + 1),
            profile=profile,
            week_two_summary=summary,
        )
        if args.apply:
            scoring = run_league_scoring_recalculation(
                db, league_id=None, season=args.season, week=2, provider="espn"
            )
            db.commit()
            report.update({"mode": "applied", "scoring": scoring})
        else:
            db.rollback()
            report["mode"] = "dry_run"
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
