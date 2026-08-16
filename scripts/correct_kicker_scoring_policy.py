#!/usr/bin/env python3
"""Dry-run or apply the official 3/3/4/5/5 kicker-scoring correction."""

from __future__ import annotations

import argparse
import json

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.kicker_scoring_policy_correction import (
    apply_kicker_scoring_policy_correction,
    render_kicker_scoring_policy_correction_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--apply", action="store_true", help="Apply proven eligible plans. Default is dry-run.")
    args = parser.parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        if not args.apply:
            print(json.dumps(render_kicker_scoring_policy_correction_plan(db, season=args.season), indent=2, sort_keys=True, default=str))
            return
        try:
            result = apply_kicker_scoring_policy_correction(db, season=args.season)
            db.commit()
        except Exception:
            db.rollback()
            raise
        print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
