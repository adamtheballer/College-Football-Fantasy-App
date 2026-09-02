#!/usr/bin/env python3
"""Apply Tennessee's official Faizon Brandon starting-QB correction.

Source: Tennessee Athletics, Aug. 25, 2026.  This job never rewrites the
sealed preseason workbooks; it records a versioned official role correction
that takes precedence on all public projection reads.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.official_role_corrections import apply_tennessee_qb_starter_correction


OFFICIAL_SOURCE_URL = (
    "https://utsports.com/news/2026/8/25/football-vols-begin-mock-game-week-freshman-faizon-brandon-named-qb-starter"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--start-week", type=int, default=1)
    parser.add_argument("--end-week", type=int, default=13)
    parser.add_argument("--apply", action="store_true", help="Persist; default is an auditable dry run.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.end_week < args.start_week:
        raise ValueError("--end-week cannot be before --start-week.")
    ensure_models_registered()
    with SessionLocal() as db:
        result = apply_tennessee_qb_starter_correction(
            db,
            season=args.season,
            weeks=range(args.start_week, args.end_week + 1),
            source_url=OFFICIAL_SOURCE_URL,
        )
        if args.apply:
            db.commit()
            result["mode"] = "applied"
        else:
            db.rollback()
            result["mode"] = "dry_run"
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
