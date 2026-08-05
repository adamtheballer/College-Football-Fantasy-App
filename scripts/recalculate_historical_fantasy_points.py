#!/usr/bin/env python3
"""Backfill canonical standard fantasy points for every stored historical season.

This command never fetches a provider or changes raw stat fields.  It only
recomputes the derived player-card total with the league-independent standard
scoring contract.  Run with --apply after reviewing the default dry-run report.
"""

from __future__ import annotations

import argparse
import json

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.services.historical_stats import apply_standard_historical_fantasy_points


def recalculate(*, apply: bool) -> dict[str, int | bool]:
    ensure_models_registered()
    with SessionLocal() as db:
        rows = db.query(PlayerHistoricalSeasonStat).order_by(PlayerHistoricalSeasonStat.id).all()
        changed = 0
        for row in rows:
            if apply_standard_historical_fantasy_points(row):
                changed += 1
        if apply:
            db.commit()
        else:
            db.rollback()
        return {"apply": apply, "historical_seasons": len(rows), "updated": changed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist the calculated standard fantasy points.")
    args = parser.parse_args()
    print(json.dumps(recalculate(apply=args.apply), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
