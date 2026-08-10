#!/usr/bin/env python3
"""Preview or explicitly publish reviewed PRESEASON_WEEKLY_V1 projections.

This is deliberately a separate operator command. It never generates rows and
it is read-only unless ``--apply`` is present.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from sqlalchemy import select

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from scripts.import_preseason_weekly_projections import MODEL_VERSION, sealed_annual_baseline_source


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument(
        "--annual-source-hash",
        required=True,
        help="SHA-256 of the sealed annual-projection export used to build the PRESEASON rows.",
    )
    parser.add_argument("--player-id", type=int, action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    expected_source = sealed_annual_baseline_source(args.annual_source_hash)
    ensure_models_registered()
    report = {"mode": "apply" if args.apply else "preview", "approved": [], "blocked": []}
    with SessionLocal() as db:
        rows = db.scalars(select(WeeklyProjection).where(
            WeeklyProjection.season == args.season,
            WeeklyProjection.week == args.week,
            WeeklyProjection.player_id.in_(args.player_id),
            WeeklyProjection.projection_version == "PRESEASON",
        )).all()
        by_player = {row.player_id: row for row in rows}
        for player_id in args.player_id:
            row = by_player.get(player_id)
            reasons = []
            if row is None: reasons.append("missing_authoritative_projection")
            else:
                if row.model_version != MODEL_VERSION: reasons.append("wrong_model_version")
                if row.baseline_source != expected_source: reasons.append("wrong_sealed_source")
                if row.projection_status != "ACTIVE": reasons.append("projection_not_active")
                if row.team_id is None or row.opponent_team_id is None: reasons.append("missing_canonical_team_or_opponent")
                if not math.isfinite(row.fantasy_points): reasons.append("non_finite_fantasy_points")
            (report["blocked"] if reasons else report["approved"]).append({"player_id": player_id, "reasons": reasons})
        if report["blocked"]:
            db.rollback()
        elif args.apply:
            for row in rows: row.is_published = True
            db.commit()
        else:
            db.rollback()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"mode": report["mode"], "approved": len(report["approved"]), "blocked": len(report["blocked"])}, sort_keys=True))
    return 0 if not report["blocked"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
