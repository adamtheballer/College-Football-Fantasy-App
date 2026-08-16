#!/usr/bin/env python3
"""Read-only production companion for ESPN public-scoring release review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.services.live_scoring_readiness import (
    flat_field_goal_league_audit,
    public_scoring_preflight,
    scoring_operations_report,
)
from scripts.audit_espn_live_readiness import build_readiness_report
from scripts.import_espn_live_identities import _review_priority


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only ESPN public live-scoring readiness audit.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--event-fixture", type=Path, help="Optional captured ESPN scoreboard fixture for strict event verification.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        readiness = build_readiness_report(db, season=args.season, event_fixture=args.event_fixture)
        groups = {key: [] for key in ("unresolved_starting", "unresolved_rostered_bench", "unresolved_free_agents", "unresolved_no_current_fantasy_exposure")}
        for item in readiness["players"]["remediation_players"]:
            player_id = item["player_id"]
            active_rosters = (
                db.query(RosterEntry.league_id)
                .join(League, League.id == RosterEntry.league_id)
                .filter(RosterEntry.player_id == player_id, RosterEntry.status == "active", League.status.notin_(("cancelled", "archived")))
                .distinct()
                .all()
            )
            starter_leagues = (
                db.query(LineupWeekSnapshot.league_id)
                .filter(
                    LineupWeekSnapshot.player_id == player_id,
                    LineupWeekSnapshot.season == args.season,
                    LineupWeekSnapshot.week == args.week,
                    LineupWeekSnapshot.is_starter.is_(True),
                )
                .distinct()
                .all()
            )
            enriched = {
                **item,
                "review_priority": _review_priority(db.get(Player, player_id)),
                "official_league_count": len(active_rosters),
                "starting_league_count": len(starter_leagues),
            }
            if starter_leagues:
                groups["unresolved_starting"].append(enriched)
            elif active_rosters:
                groups["unresolved_rostered_bench"].append(enriched)
            else:
                groups["unresolved_free_agents"].append(enriched)
        output = {
            "season": args.season,
            "week": args.week,
            "identity": readiness["players"],
            "games": readiness["games"],
            "fantasy_exposure": {key: {"count": len(value), "players": value} for key, value in groups.items()},
            "preflight": public_scoring_preflight(db, season=args.season, week=args.week),
            "operations": scoring_operations_report(db, season=args.season, week=args.week),
            "flat_field_goals": flat_field_goal_league_audit(db, season=args.season),
        }
    print(json.dumps(output, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
