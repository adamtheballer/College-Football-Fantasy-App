#!/usr/bin/env python3
"""Preview the reviewed ASU RB correction; persist only with --apply."""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.services.cardae_mack_correction import ASU_ESPN_ID, MACK_ESPN_ID, apply_cardae_mack_correction
from scripts.bootstrap_canonical_player_data import projection_stats_for_row


def role_baselines() -> dict[int, dict]:
    path = Path(__file__).resolve().parents[1] / "reports/source-imports/2026/player-projections.csv"
    rows = list(csv.DictReader(path.open()))
    result = {}
    for source_slot, target_slot, name in (("RB2", 2, "Demarius Robinson"), ("RB3", 3, "Jason Brown Jr.")):
        matches = [r for r in rows if r["TEAM"].upper() == "ARIZONA STATE" and r["POSITION"] == source_slot and r["PLAYER"] == name]
        if len(matches) != 1:
            raise ValueError(f"Immutable reviewed ASU slot baseline is missing: {source_slot}.")
        result[target_slot] = projection_stats_for_row(matches[0])
    return result


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int, default=8)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    ensure_models_registered()
    with SessionLocal() as db:
        games = db.query(Game).filter(Game.season == 2026, Game.week <= args.week,
            Game.schedule_status.in_(("final", "post")),
            (Game.home_team == "Arizona State") | (Game.away_team == "Arizona State")).order_by(Game.week).all()
        event_ids = [g.external_id for g in games]
    with ESPNClient() as client:
        profile = deepcopy(client.get_athlete_profile(MACK_ESPN_ID))
        roster = client.get_team_roster(ASU_ESPN_ID)
        matches = [a for group in roster.get("athletes", []) for a in group.get("items", []) if str(a.get("id")) == MACK_ESPN_ID]
        if len(matches) != 1:
            raise ValueError("Exact Mack identity is missing from ASU's current ESPN roster.")
        for field in ("birthPlace", "headshot", "displayHeight", "displayWeight", "jersey"):
            if matches[0].get(field) is not None:
                profile["athlete"][field] = matches[0][field]
        summaries = [client.get_summary(event_id) for event_id in event_ids]
    with SessionLocal() as db:
        result = apply_cardae_mack_correction(db, season=2026, effective_week=args.week,
            profile=profile, summaries=summaries, role_baselines=role_baselines())
        if args.apply:
            db.commit()
        else:
            db.rollback()
        return {**result, "mode": "applied" if args.apply else "preview"}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
