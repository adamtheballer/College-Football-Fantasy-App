#!/usr/bin/env python3
"""Apply the reviewed Jamal Rule Nebraska RB1 correction.

Default mode is read-only: it fetches the exact ESPN profile and completed
Week 1 box score, validates them, then rolls the transaction back. ``--apply``
is idempotent and also refreshes scoring and the Week 2 outlook after the
verified Week 1 row is present.
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
from collegefootballfantasy_api.app.services.jamal_rule_correction import (
    JAMAL_RULE_ESPN_ID,
    NEBRASKA_WEEK_ONE_EVENT_ID,
    apply_jamal_rule_nebraska_correction,
)
from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation
from collegefootballfantasy_api.app.services.weekly_outlook_refresh import refresh_post_final_outlook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--end-week", type=int, default=13)
    parser.add_argument("--apply", action="store_true", help="Persist after the exact ESPN identity and final box score validate.")
    return parser.parse_args()


def _enrich_profile_from_current_roster(
    profile: dict, roster_payload: dict,
) -> dict:
    """Fill public profile gaps (notably birthplace/headshot) from ESPN roster.

    ESPN's athlete endpoint omits fields for some college players even when
    the team roster supplies them. Preserve the exact verified athlete ID and
    only copy fields from that same roster entry.
    """

    enriched = deepcopy(profile)
    athlete = enriched.get("athlete") if isinstance(enriched.get("athlete"), dict) else None
    groups = roster_payload.get("athletes") if isinstance(roster_payload, dict) else None
    roster_rows = [
        item
        for group in (groups or [])
        if isinstance(group, dict)
        for item in (group.get("items") or [])
        if isinstance(item, dict) and str(item.get("id") or "") == JAMAL_RULE_ESPN_ID
    ]
    if athlete is None or len(roster_rows) != 1:
        return enriched
    roster_row = roster_rows[0]
    for field in ("birthPlace", "headshot", "displayHeight", "displayWeight", "jersey"):
        if roster_row.get(field) is not None:
            athlete[field] = roster_row[field]
    return enriched


def main() -> int:
    args = parse_args()
    if not 1 <= args.end_week <= 13:
        raise ValueError("--end-week must be between 1 and 13.")
    ensure_models_registered()
    with ESPNClient() as espn:
        profile = espn.get_athlete_profile(JAMAL_RULE_ESPN_ID)
        roster = espn.get_team_roster("158")
        profile = _enrich_profile_from_current_roster(profile, roster)
        summary = espn.get_summary(NEBRASKA_WEEK_ONE_EVENT_ID)

    with SessionLocal() as db:
        report = apply_jamal_rule_nebraska_correction(
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
