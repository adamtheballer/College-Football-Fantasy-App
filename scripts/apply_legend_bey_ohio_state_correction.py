#!/usr/bin/env python3
"""Apply the reviewed Legend Bey Ohio State RB3 replacement.

The default invocation is read-only.  ``--apply`` persists only after the
exact ESPN identity and final Week 1 box score are verified, then refreshes
league scoring and the post-final Week 2 outlook.
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
from collegefootballfantasy_api.app.services.fantasy_week_finality import week_is_authoritatively_finalized
from collegefootballfantasy_api.app.services.legend_bey_correction import (
    LEGEND_BEY_ESPN_ID,
    OHIO_STATE_ESPN_TEAM_ID,
    OHIO_STATE_WEEK_ONE_EVENT_ID,
    apply_legend_bey_ohio_state_correction,
)
from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation
from collegefootballfantasy_api.app.services.weekly_outlook_refresh import refresh_post_final_outlook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--end-week", type=int, default=13)
    parser.add_argument("--apply", action="store_true", help="Persist after exact ESPN identity and final box-score validation.")
    return parser.parse_args()


def _enrich_profile_from_current_roster(profile: dict, roster_payload: dict) -> dict:
    """Copy public bio fields only from the same verified ESPN roster identity."""
    enriched = deepcopy(profile)
    athlete = enriched.get("athlete") if isinstance(enriched.get("athlete"), dict) else None
    groups = roster_payload.get("athletes") if isinstance(roster_payload, dict) else None
    matching_rows = [
        item
        for group in (groups or [])
        if isinstance(group, dict)
        for item in (group.get("items") or [])
        if isinstance(item, dict) and str(item.get("id") or "") == LEGEND_BEY_ESPN_ID
    ]
    if athlete is None or len(matching_rows) != 1:
        return enriched
    for field in ("birthPlace", "headshot", "displayHeight", "displayWeight", "jersey"):
        if matching_rows[0].get(field) is not None:
            athlete[field] = matching_rows[0][field]
    return enriched


def main() -> int:
    args = parse_args()
    if not 1 <= args.end_week <= 13:
        raise ValueError("--end-week must be between 1 and 13.")
    ensure_models_registered()
    with ESPNClient() as espn:
        profile = espn.get_athlete_profile(LEGEND_BEY_ESPN_ID)
        profile = _enrich_profile_from_current_roster(
            profile, espn.get_team_roster(OHIO_STATE_ESPN_TEAM_ID)
        )
        summary = espn.get_summary(OHIO_STATE_WEEK_ONE_EVENT_ID)

    with SessionLocal() as db:
        report = apply_legend_bey_ohio_state_correction(
            db,
            season=args.season,
            role_weeks=range(1, args.end_week + 1),
            profile=profile,
            week_one_summary=summary,
        )
        if args.apply:
            scoring = run_league_scoring_recalculation(
                db, league_id=None, season=args.season, week=1, provider="espn"
            )
            outlook = None
            if week_is_authoritatively_finalized(db, season=args.season, week=1):
                outlook = refresh_post_final_outlook(db, season=args.season, completed_week=1)
            db.commit()
            report.update({"mode": "applied", "scoring": scoring, "outlook": outlook})
        else:
            db.rollback()
            report["mode"] = "dry_run"
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
