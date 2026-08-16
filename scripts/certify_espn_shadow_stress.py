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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock

import httpx
from sqlalchemy import func

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.espn_live_scoring import espn_week_freshness, run_espn_scoring_cycle


NOW = datetime(2026, 8, 29, 17, 0, tzinfo=timezone.utc)


class FakeESPN:
    def __init__(self) -> None:
        self.scoreboard_calls = 0
        self.summary_calls = 0
        self._lock = Lock()

    def get_scoreboard_events(self, *, season: int, week: int) -> list[dict]:
        with self._lock:
            self.scoreboard_calls += 1
        return [{"id": "401-stress", "status": {"type": {"state": "in", "completed": False}}, "competitions": [{"competitors": [{"team": {"location": "Texas"}}]}]}]

    def get_summary(self, event_id: str) -> dict:
        with self._lock:
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


class TimeoutESPN(FakeESPN):
    """Recorded failure path; it never makes a network request."""

    def get_summary(self, event_id: str) -> dict:
        with self._lock:
            self.summary_calls += 1
        raise httpx.TimeoutException("certification provider timeout")


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

        # Real PostgreSQL lease race: two independently-created sessions try to
        # process the same due event. SKIP LOCKED must allow exactly one
        # summary request and one successful game. Discovery is held fresh so
        # this tests the per-game claim, not duplicate schedule discovery.
        race_at = NOW + timedelta(seconds=360)
        poll = (
            db.query(ProviderGamePoll)
            .filter_by(provider="espn", provider_game_id="401-stress")
            .one()
        )
        discovery = (
            db.query(ProviderGamePoll)
            .filter_by(provider="espn", provider_game_id="discovery:2026:1")
            .one()
        )
        poll.next_poll_at = race_at
        discovery.next_poll_at = race_at + timedelta(seconds=180)
        db.commit()

        def run_worker(worker_id: str):
            with SessionLocal() as worker_db:
                return run_espn_scoring_cycle(
                    worker_db,
                    season=2026,
                    week=1,
                    mode="shadow",
                    client=provider,
                    worker_id=worker_id,
                    now=race_at,
                )

        before_race_summaries = provider.summary_calls
        with ThreadPoolExecutor(max_workers=2) as executor:
            raced = list(executor.map(run_worker, ("stress-race-a", "stress-race-b")))
        if (
            sum(result.successful_games for result in raced) != 1
            or provider.summary_calls != before_race_summaries + 1
        ):
            raise AssertionError("two PostgreSQL workers must produce exactly one game fetch")

        # A timeout must delay only that durable game poll. A second worker
        # inside the retry window must not repeat the provider call.
        failure_at = race_at + timedelta(seconds=180)
        with SessionLocal() as failure_db:
            timed_out = run_espn_scoring_cycle(
                failure_db,
                season=2026,
                week=1,
                mode="shadow",
                client=TimeoutESPN(),
                worker_id="stress-timeout",
                now=failure_at,
            )
            if timed_out.failed_games != 1:
                raise AssertionError("timeout must fail the claimed game")
            retried = run_espn_scoring_cycle(
                failure_db,
                season=2026,
                week=1,
                mode="shadow",
                client=TimeoutESPN(),
                worker_id="stress-timeout-retry",
                now=failure_at + timedelta(seconds=30),
            )
            if retried.claimed_games != 0:
                raise AssertionError("timeout retry window must not immediately re-fetch the game")
        print(
            json.dumps(
                {
                    "league_count": league_count,
                    "roster_count": roster_count,
                    "provider_summary_fetches": provider.summary_calls,
                    "provider_scoreboard_fetches": provider.scoreboard_calls,
                    "poll_work_items": first.claimed_games + boundary.claimed_games,
                    "minimum_successful_fetch_gap_seconds": 180,
                    "two_worker_race_successful_games": sum(result.successful_games for result in raced),
                    "timeout_retry_claims_within_30_seconds": retried.claimed_games,
                    "duration_seconds": round(time.monotonic() - started, 3),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
