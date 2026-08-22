"""Dry-run-first audit/backfill of league postseason plans.

The default mode performs no writes. ``--apply`` may create missing planned
settings only when doing so cannot conflict with an already-started/final
matchup; it never deletes or rewrites scheduled games.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.postseason import LeaguePostseasonSettings
from collegefootballfantasy_api.app.services.postseason_service import get_or_create_postseason_settings, postseason_calendar


def _plan_fields(plan: dict) -> dict:
    return {
        key: plan[key]
        for key in (
            "regular_season_start_week", "regular_season_end_week", "playoff_start_week", "championship_week",
            "rounds", "calendar_policy_version", "calendar_source_identity", "calendar_source_revision",
            "calendar_source_sha256", "calendar_source_format_version",
        )
        if key in plan
    }


def audit(*, apply: bool = False) -> dict:
    report: dict[str, list[dict]] = {"ready": [], "review_required": [], "created": [], "calendar_blocked": []}
    with SessionLocal() as db:
        for league in db.query(League).order_by(League.id).all():
            existing = db.query(LeaguePostseasonSettings).filter(
                LeaguePostseasonSettings.league_id == league.id,
                LeaguePostseasonSettings.season == league.season_year,
            ).one_or_none()
            try:
                from collegefootballfantasy_api.app.models.league_settings import LeagueSettings

                settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).one_or_none()
                expected_plan = postseason_calendar(db, league, int(settings.playoff_teams if settings else 4))
                # ``get_or_create`` is only used in explicit apply mode. The
                # dry run always reports its expected reservation without a
                # write, including for existing historical plans.
                if existing is None and apply:
                    get_or_create_postseason_settings(db, league)
            except ValueError as exc:
                report["calendar_blocked"].append({"league_id": league.id, "reason": str(exc)})
                continue
            occupied = db.query(Matchup).filter(
                Matchup.league_id == league.id,
                Matchup.season == league.season_year,
                Matchup.week >= expected_plan["playoff_start_week"],
            ).all()
            started = [row.id for row in occupied if (row.status or "").lower() in {"live", "in_progress", "final", "completed", "stat_corrected"}]
            if started:
                report["review_required"].append({"league_id": league.id, "reason": "started/final matchup occupies reserved postseason week", "matchup_ids": started})
                continue
            if occupied:
                report["review_required"].append({
                    "league_id": league.id,
                    "reason": "future regular-season matchup occupies reserved postseason week; manual review required",
                    "matchup_ids": [row.id for row in occupied],
                })
                continue
            item = {
                "league_id": league.id,
                "season": league.season_year,
                "expected_calendar": _plan_fields(expected_plan),
                "current_calendar": ({
                    "regular_season_start_week": existing.regular_season_start_week,
                    "regular_season_end_week": existing.regular_season_end_week,
                    "playoff_start_week": existing.playoff_start_week,
                    "championship_week": existing.championship_week,
                    "calendar_policy_version": existing.calendar_policy_version,
                    "calendar_source_identity": existing.calendar_source_identity,
                    "calendar_source_revision": existing.calendar_source_revision,
                    "calendar_source_sha256": existing.calendar_source_sha256,
                    "calendar_source_format_version": existing.calendar_source_format_version,
                } if existing else None),
            }
            if existing is None and apply:
                report["created"].append(item)
            else:
                report["ready"].append(item)
        if apply:
            db.commit()
        else:
            db.rollback()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit postseason schedule readiness without mutating production data.")
    parser.add_argument("--apply", action="store_true", help="Create only missing, safe planned settings; never delete or rewrite matchups.")
    args = parser.parse_args()
    print(json.dumps(audit(apply=args.apply), indent=2, sort_keys=True))
