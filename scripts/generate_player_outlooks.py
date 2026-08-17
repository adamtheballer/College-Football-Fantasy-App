"""Generate auditable preseason player outlooks from local canonical data only.

This script defaults to dry-run. Pass --apply only after reviewing the emitted
artifact; it never calls a provider or an LLM.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.player_season_outlook import (
    PLAYER_OUTLOOK_GENERATOR_VERSION,
    SUPPORTED_POSITIONS,
    build_player_season_outlook_facts,
    generate_player_season_outlook,
    persist_player_season_outlook,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic player outlook records.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--apply", action="store_true", help="Persist generated rows after review.")
    parser.add_argument("--review-output", type=Path, default=None)
    args = parser.parse_args()
    review_output = args.review_output or Path(f"/private/tmp/player-season-outlooks-{args.season}.json")

    ensure_models_registered()
    session = SessionLocal()
    try:
        players = session.query(Player).filter(Player.position.in_(sorted(SUPPORTED_POSITIONS))).order_by(
            Player.position.asc(), Player.name.asc()
        ).all()
        counts: Counter[str] = Counter()
        results: list[dict] = []
        for player in players:
            facts = build_player_season_outlook_facts(session, player, season_year=args.season)
            generated = generate_player_season_outlook(facts)
            counts[generated.status] += 1
            results.append({
                "player_id": player.id,
                "name": player.name,
                "position": player.position,
                "status": generated.status,
                "validation_errors": generated.validation_errors,
                "outlook": generated.text,
                "facts": generated.facts,
            })
            if args.apply:
                persist_player_season_outlook(
                    session,
                    player_id=player.id,
                    season_year=args.season,
                    generated=generated,
                    generator_version=PLAYER_OUTLOOK_GENERATOR_VERSION,
                )
        if args.apply:
            session.commit()
        review_output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "mode": "apply" if args.apply else "dry_run",
            "season": args.season,
            "players_considered": len(players),
            "status_counts": dict(sorted(counts.items())),
            "review_output": str(review_output),
            "generator_version": PLAYER_OUTLOOK_GENERATOR_VERSION,
        }, sort_keys=True))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
