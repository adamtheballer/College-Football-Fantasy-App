#!/usr/bin/env python3
"""Guarded disposable-PostgreSQL cache certification for ESPN shadow mode.

This script is intentionally refused unless CI explicitly opts in.  It never
uses the real ESPN client and is designed only for a fresh disposable database.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.espn_live_scoring import espn_week_freshness, run_espn_scoring_cycle


NOW = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)


class FakeESPN:
    def __init__(self) -> None:
        self.scoreboard_calls = 0
        self.summary_calls = 0

    def get_scoreboard_events(self, *, season: int, week: int) -> list[dict]:
        self.scoreboard_calls += 1
        return [{"id": "401-stress", "status": {"type": {"state": "in", "completed": False}}, "competitions": [{"competitors": [{"team": {"location": "Texas"}}]}]}]

    def get_summary(self, event_id: str) -> dict:
        self.summary_calls += 1
        return {
            "event_id": event_id,
            "boxscore": {
                "players": [
                    {
                        "team": {"location": "Texas", "displayName": "Texas Longhorns"},
                        "statistics": [
                            {
                                "name": "passing",
                                "keys": ["passingYards", "passingTouchdowns", "interceptions"],
                                "athletes": [{"athlete": {"id": "unmapped-stress-qb", "displayName": "Stress QB"}, "stats": ["100", "1", "0"]}],
                            }
                        ],
                    }
                ]
            },
        }


def _require_disposable_opt_in() -> None:
    if os.getenv("CFF_ALLOW_SHADOW_STRESS_CERTIFICATION") != "1":
        raise SystemExit("Refusing stress certification without CFF_ALLOW_SHADOW_STRESS_CERTIFICATION=1")


def main() -> None:
    _require_disposable_opt_in()
    ensure_models_registered()
    suffix = uuid.uuid4().hex[:12]
    started = time.monotonic()
    with SessionLocal() as db:
        players = [Player(name=f"Shadow stress player {suffix}-{index}", position="WR", school="Texas") for index in range(10)]
        db.add_all(players)
        db.flush()
        for league_index in range(100):
            league = League(name=f"ESPN shadow stress {suffix}-{league_index}", season_year=2026, max_teams=1)
            db.add(league)
            db.flush()
            team = Team(league_id=league.id, name=f"Shadow stress team {suffix}-{league_index}")
            db.add(team)
            db.flush()
            db.add_all(
                RosterEntry(league_id=league.id, team_id=team.id, player_id=player.id, slot="BE", status="active")
                for player in players
            )
        db.commit()

        league_count = db.query(func.count(League.id)).filter(League.name.like(f"ESPN shadow stress {suffix}-%")).scalar()
        roster_count = (
            db.query(func.count(RosterEntry.id))
            .join(League, League.id == RosterEntry.league_id)
            .filter(League.name.like(f"ESPN shadow stress {suffix}-%"))
            .scalar()
        )
        if league_count != 100 or roster_count != 1000:
            raise AssertionError(f"expected 100 leagues and 1000 rosters, got {league_count} and {roster_count}")

        provider = FakeESPN()
        first = run_espn_scoring_cycle(db, season=2026, week=1, mode="shadow", client=provider, worker_id="stress-a", now=NOW)
        if first.successful_games != 1 or provider.summary_calls != 1:
            raise AssertionError("initial due game must fetch exactly once")
        for offset in (30, 60, 90, 120, 150, 179):
            for _ in range(100):
                espn_week_freshness(db, season=2026, week=1, now=NOW + timedelta(seconds=offset))
            result = run_espn_scoring_cycle(
                db, season=2026, week=1, mode="shadow", client=provider, worker_id=f"stress-before-{offset}", now=NOW + timedelta(seconds=offset)
            )
            if result.claimed_games or provider.summary_calls != 1:
                raise AssertionError(f"provider was fetched before the 180-second boundary at T={offset}")
        boundary = run_espn_scoring_cycle(
            db, season=2026, week=1, mode="shadow", client=provider, worker_id="stress-b", now=NOW + timedelta(seconds=180)
        )
        if boundary.successful_games != 1 or provider.summary_calls != 2:
            raise AssertionError("one second provider fetch must be permitted at the 180-second boundary")
        print(
            json.dumps(
                {
                    "league_count": league_count,
                    "roster_count": roster_count,
                    "provider_summary_fetches": provider.summary_calls,
                    "provider_scoreboard_fetches": provider.scoreboard_calls,
                    "poll_work_items": first.claimed_games + boundary.claimed_games,
                    "minimum_successful_fetch_gap_seconds": 180,
                    "duration_seconds": round(time.monotonic() - started, 3),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
