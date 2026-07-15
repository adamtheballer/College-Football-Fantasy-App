from __future__ import annotations

import argparse
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.services.trade_service import process_trade_offers_once
from collegefootballfantasy_api.app.services.waiver_service import process_waiver_claims_once


def _seed_due_work() -> dict[str, int]:
    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        proposing_user = User(
            email=f"stress-proposing-{suffix}@example.com",
            first_name="Stress Proposing",
            password_hash="not-used",
            api_token=f"stress-proposing-{suffix}",
            email_verified_at=now,
        )
        receiving_user = User(
            email=f"stress-receiving-{suffix}@example.com",
            first_name="Stress Receiving",
            password_hash="not-used",
            api_token=f"stress-receiving-{suffix}",
            email_verified_at=now,
        )
        db.add_all([proposing_user, receiving_user])
        db.flush()

        league = League(
            name=f"Postgres lifecycle stress {suffix}",
            season_year=2026,
            commissioner_user_id=proposing_user.id,
            max_teams=2,
        )
        db.add(league)
        db.flush()
        db.add(
            LeagueSettings(
                league_id=league.id,
                roster_slots_json={"QB": 1, "RB": 1, "WR": 1},
                waiver_type="faab",
                waiver_period_hours=24,
                trade_review_type="none",
            )
        )

        proposing_team = Team(
            league_id=league.id,
            name=f"Stress Proposing {suffix}",
            owner_user_id=proposing_user.id,
            owner_name="Stress Proposing",
        )
        receiving_team = Team(
            league_id=league.id,
            name=f"Stress Receiving {suffix}",
            owner_user_id=receiving_user.id,
            owner_name="Stress Receiving",
        )
        db.add_all([proposing_team, receiving_team])
        db.flush()

        giving_player = Player(name=f"Stress QB {suffix}", school="Stress U", position="QB")
        receiving_player = Player(name=f"Stress RB {suffix}", school="Stress U", position="RB")
        waiver_player = Player(name=f"Stress WR {suffix}", school="Stress U", position="WR")
        db.add_all([giving_player, receiving_player, waiver_player])
        db.flush()
        db.add_all(
            [
                RosterEntry(
                    league_id=league.id,
                    team_id=proposing_team.id,
                    player_id=giving_player.id,
                    slot="QB",
                    status="active",
                ),
                RosterEntry(
                    league_id=league.id,
                    team_id=receiving_team.id,
                    player_id=receiving_player.id,
                    slot="RB",
                    status="active",
                ),
            ]
        )
        trade = TradeOffer(
            league_id=league.id,
            proposing_team_id=proposing_team.id,
            receiving_team_id=receiving_team.id,
            created_by_user_id=proposing_user.id,
            status="accepted_pending",
            accepted_at=now - timedelta(minutes=2),
            process_after=now - timedelta(minutes=1),
        )
        db.add(trade)
        db.flush()
        db.add_all(
            [
                TradeOfferItem(trade_offer_id=trade.id, team_id=proposing_team.id, player_id=giving_player.id),
                TradeOfferItem(trade_offer_id=trade.id, team_id=receiving_team.id, player_id=receiving_player.id),
            ]
        )
        db.add(
            WaiverClaim(
                league_id=league.id,
                team_id=proposing_team.id,
                add_player_id=waiver_player.id,
                created_by_user_id=proposing_user.id,
                status="pending",
                priority_snapshot=1,
                faab_bid=7,
                process_after=now - timedelta(minutes=1),
            )
        )
        db.commit()
        return {
            "league_id": league.id,
            "trade_id": trade.id,
            "waiver_player_id": waiver_player.id,
            "proposing_team_id": proposing_team.id,
            "receiving_team_id": receiving_team.id,
            "giving_player_id": giving_player.id,
            "receiving_player_id": receiving_player.id,
        }


def _run_worker(start: threading.Barrier) -> dict[str, dict[str, int]]:
    start.wait(timeout=15)
    with SessionLocal() as db:
        return {
            "waivers": process_waiver_claims_once(db),
            "trades": process_trade_offers_once(db),
        }


def _assert_exactly_once(seed: dict[str, int], results: list[dict[str, dict[str, int]]]) -> dict[str, int]:
    with SessionLocal() as db:
        trade = db.get(TradeOffer, seed["trade_id"])
        waiver_entry_count = (
            db.query(RosterEntry)
            .filter(
                RosterEntry.league_id == seed["league_id"],
                RosterEntry.player_id == seed["waiver_player_id"],
            )
            .count()
        )
        giving_entry = (
            db.query(RosterEntry)
            .filter(
                RosterEntry.league_id == seed["league_id"],
                RosterEntry.player_id == seed["giving_player_id"],
            )
            .one()
        )
        receiving_entry = (
            db.query(RosterEntry)
            .filter(
                RosterEntry.league_id == seed["league_id"],
                RosterEntry.player_id == seed["receiving_player_id"],
            )
            .one()
        )
        spent = db.scalar(
            db.query(func.coalesce(WaiverPriority.faab_spent, 0))
            .filter(
                WaiverPriority.league_id == seed["league_id"],
                WaiverPriority.team_id == seed["proposing_team_id"],
            )
            .statement
        )

    assert trade is not None and trade.status == "processed", f"due trade did not process: {trade.status if trade else None}; workers={results}"
    assert giving_entry.team_id == seed["receiving_team_id"], "giving player did not move to receiving roster"
    assert receiving_entry.team_id == seed["proposing_team_id"], "receiving player did not move to proposing roster"
    assert waiver_entry_count == 1, "waiver player was added more than once"
    assert spent == 7, "FAAB was not deducted exactly once"
    assert sum(result["trades"]["processed"] for result in results) == 1, f"trade worker result mismatch: {results}"
    assert sum(result["waivers"]["processed"] for result in results) == 1, f"waiver worker result mismatch: {results}"
    return {"workers": len(results), "trade_processed": 1, "waiver_processed": 1, "faab_spent": int(spent)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the lifecycle-worker locking stress test against PostgreSQL.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent worker sessions to launch.")
    args = parser.parse_args()
    workers = max(2, args.workers)
    seed = _seed_due_work()
    barrier = threading.Barrier(workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_run_worker, [barrier] * workers))
    print(_assert_exactly_once(seed, results))


if __name__ == "__main__":
    main()
