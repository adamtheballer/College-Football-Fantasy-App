#!/usr/bin/env python3
"""Dry-run-first repair for early Week 0 player-game schedule data."""

from __future__ import annotations

import argparse
import json

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.early_game_schedule_reconciliation import (
    reconcile_early_player_game_schedules,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument(
        "--team",
        action="append",
        default=[],
        help="Restrict the repair to a verified team (repeatable).",
    )
    parser.add_argument("--apply", action="store_true", help="Persist only the reviewed reconciliation plan.")
    args = parser.parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        report = reconcile_early_player_game_schedules(
            db,
            season=args.season,
            apply=args.apply,
            teams=set(args.team) or None,
        )
        if args.apply:
            db.commit()
        else:
            db.rollback()
    print(json.dumps(report.__dict__, indent=2, sort_keys=True))
    return 0 if not report.unresolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
