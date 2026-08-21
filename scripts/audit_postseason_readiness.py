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


def audit(*, apply: bool = False) -> dict:
    report: dict[str, list[dict]] = {"ready": [], "review_required": [], "created": []}
    with SessionLocal() as db:
        for league in db.query(League).order_by(League.id).all():
            existing = db.query(LeaguePostseasonSettings).filter(
                LeaguePostseasonSettings.league_id == league.id,
                LeaguePostseasonSettings.season == league.season_year,
            ).one_or_none()
            try:
                # ``get_or_create`` is only used in explicit apply mode; dry
                # run computes the expected reservation without a write.
                if existing is None and not apply:
                    from collegefootballfantasy_api.app.models.league_settings import LeagueSettings

                    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).one_or_none()
                    plan = postseason_calendar(db, league, int(settings.playoff_teams if settings else 4))
                else:
                    plan_row = existing or get_or_create_postseason_settings(db, league)
                    plan = {"regular_season_end_week": plan_row.regular_season_end_week, "playoff_start_week": plan_row.playoff_start_week}
            except ValueError as exc:
                report["review_required"].append({"league_id": league.id, "reason": str(exc)})
                continue
            occupied = db.query(Matchup).filter(
                Matchup.league_id == league.id,
                Matchup.season == league.season_year,
                Matchup.week >= plan["playoff_start_week"],
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
            item = {"league_id": league.id, **plan}
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
