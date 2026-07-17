from __future__ import annotations

import argparse
import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.schemas.trade import TradeActionRequest
from collegefootballfantasy_api.app.services.draft_service import process_expired_draft_picks_once
from collegefootballfantasy_api.app.services.trade_service import (
    accept_trade_offer,
    cancel_trade_offer,
    commissioner_veto_trade,
    process_trade_offers_once,
)
from collegefootballfantasy_api.app.services.waiver_service import process_waiver_claims_once
from collegefootballfantasy_api.app.services import scoring_service
from collegefootballfantasy_api.app.services.scoring_service import run_league_scoring_recalculation


def _next_monday_processing_time(now: datetime) -> datetime:
    days_until_monday = (7 - now.weekday()) % 7
    return (now + timedelta(days=days_until_monday)).replace(hour=16, minute=0, second=0, microsecond=0)


def _seed_due_work() -> dict[str, int | datetime]:
    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    process_at = _next_monday_processing_time(now)
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
                roster_slots_json={"QB": 2, "RB": 2, "WR": 2, "BENCH": 10},
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
        stale_giving_player = Player(name=f"Stress Stale WR {suffix}", school="Stress U", position="WR")
        stale_receiving_player = Player(name=f"Stress Stale QB {suffix}", school="Stress U", position="QB")
        waiver_player = Player(name=f"Stress WR {suffix}", school="Stress U", position="WR")
        draft_player = Player(name=f"Stress Draft RB {suffix}", school="Stress U", position="RB", sheet_adp=1)
        db.add_all([giving_player, receiving_player, stale_giving_player, stale_receiving_player, waiver_player, draft_player])
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
                RosterEntry(
                    league_id=league.id,
                    team_id=proposing_team.id,
                    player_id=stale_giving_player.id,
                    slot="WR",
                    status="active",
                ),
                RosterEntry(
                    league_id=league.id,
                    team_id=receiving_team.id,
                    player_id=stale_receiving_player.id,
                    slot="QB",
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
            accepted_at=process_at - timedelta(minutes=2),
            process_after=process_at - timedelta(minutes=1),
        )
        db.add(trade)
        db.flush()
        stale_trade = TradeOffer(
            league_id=league.id,
            proposing_team_id=proposing_team.id,
            receiving_team_id=receiving_team.id,
            created_by_user_id=proposing_user.id,
            status="accepted_pending",
            accepted_at=process_at - timedelta(minutes=3),
            process_after=process_at - timedelta(minutes=2),
        )
        db.add(stale_trade)
        db.flush()
        db.add_all(
            [
                TradeOfferItem(trade_offer_id=trade.id, team_id=proposing_team.id, player_id=giving_player.id),
                TradeOfferItem(trade_offer_id=trade.id, team_id=receiving_team.id, player_id=receiving_player.id),
                TradeOfferItem(trade_offer_id=stale_trade.id, team_id=proposing_team.id, player_id=stale_giving_player.id),
                TradeOfferItem(trade_offer_id=stale_trade.id, team_id=receiving_team.id, player_id=stale_receiving_player.id),
            ]
        )
        stale_entry = (
            db.query(RosterEntry)
            .filter(RosterEntry.league_id == league.id, RosterEntry.player_id == stale_giving_player.id)
            .one()
        )
        db.delete(stale_entry)
        db.add(
            WaiverClaim(
                league_id=league.id,
                team_id=proposing_team.id,
                add_player_id=waiver_player.id,
                created_by_user_id=proposing_user.id,
                status="pending",
                priority_snapshot=1,
                faab_bid=7,
                process_after=process_at - timedelta(minutes=1),
            )
        )
        draft = Draft(
            league_id=league.id,
            draft_datetime_utc=process_at - timedelta(minutes=5),
            pick_timer_seconds=1,
            status="on_clock",
            current_pick_number=1,
            current_pick_started_at=process_at - timedelta(minutes=2),
            current_pick_deadline=process_at - timedelta(minutes=1),
            draft_version=1,
        )
        db.add(draft)
        db.commit()
        return {
            "league_id": league.id,
            "trade_id": trade.id,
            "stale_trade_id": stale_trade.id,
            "waiver_player_id": waiver_player.id,
            "proposing_team_id": proposing_team.id,
            "receiving_team_id": receiving_team.id,
            "giving_player_id": giving_player.id,
            "receiving_player_id": receiving_player.id,
            "draft_id": draft.id,
            "draft_player_id": draft_player.id,
            "process_at": process_at,
        }


def _run_worker(start: threading.Barrier, process_at: datetime) -> dict[str, dict[str, int]]:
    start.wait(timeout=15)
    with SessionLocal() as db:
        return {
            "drafts": process_expired_draft_picks_once(db, now=process_at),
            "waivers": process_waiver_claims_once(db, now=process_at),
            "trades": process_trade_offers_once(db, now=process_at),
        }


def _assert_exactly_once(seed: dict[str, int | datetime], results: list[dict[str, dict[str, int]]]) -> dict[str, int]:
    with SessionLocal() as db:
        trade = db.get(TradeOffer, seed["trade_id"])
        stale_trade = db.get(TradeOffer, seed["stale_trade_id"])
        draft = db.get(Draft, seed["draft_id"])
        draft_picks = db.query(DraftPick).filter(DraftPick.draft_id == seed["draft_id"]).all()
        draft_pick_count = len(draft_picks)
        drafted_player_id = draft_picks[0].player_id if draft_pick_count == 1 else None
        draft_roster_entry_count = (
            db.query(RosterEntry)
            .filter(
                RosterEntry.league_id == seed["league_id"],
                RosterEntry.player_id == drafted_player_id,
            )
            .count()
        )
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
    assert stale_trade is not None and stale_trade.status == "failed", (
        f"failed trade did not remain isolated: {stale_trade.status if stale_trade else None}; workers={results}"
    )
    assert draft is not None and draft.status == "transition", f"due draft pick did not process: {draft.status if draft else None}; workers={results}"
    assert draft_pick_count == 1, f"due draft pick was not recorded exactly once: workers={results}"
    assert draft_roster_entry_count == 1, (
        f"drafted player was not added to exactly one roster: count={draft_roster_entry_count}; workers={results}"
    )
    assert giving_entry.team_id == seed["receiving_team_id"], "giving player did not move to receiving roster"
    assert receiving_entry.team_id == seed["proposing_team_id"], "receiving player did not move to proposing roster"
    assert waiver_entry_count == 1, "waiver player was added more than once"
    assert spent == 7, "FAAB was not deducted exactly once"
    return {
        "workers": len(results),
        "draft_auto_picked": 1,
        "trade_processed": 1,
        "trade_failed": 1,
        "waiver_processed": 1,
        "faab_spent": int(spent),
    }


def _seed_trade_transition_races() -> dict[str, int | datetime]:
    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        commissioner = User(
            email=f"stress-commissioner-{suffix}@example.com",
            first_name="Stress Commissioner",
            password_hash="not-used",
            api_token=f"stress-commissioner-{suffix}",
            email_verified_at=now,
        )
        receiver = User(
            email=f"stress-receiver-{suffix}@example.com",
            first_name="Stress Receiver",
            password_hash="not-used",
            api_token=f"stress-receiver-{suffix}",
            email_verified_at=now,
        )
        db.add_all([commissioner, receiver])
        db.flush()

        league = League(
            name=f"Postgres trade-transition stress {suffix}",
            season_year=2026,
            commissioner_user_id=commissioner.id,
            max_teams=2,
        )
        db.add(league)
        db.flush()
        db.add(
            LeagueSettings(
                league_id=league.id,
                roster_slots_json={"QB": 1, "RB": 1, "WR": 1, "TE": 1, "BENCH": 5},
                trade_review_type="none",
            )
        )
        db.add_all(
            [
                LeagueMember(league_id=league.id, user_id=commissioner.id, role="commissioner"),
                LeagueMember(league_id=league.id, user_id=receiver.id, role="manager"),
            ]
        )

        proposing_team = Team(
            league_id=league.id,
            name=f"Stress Transition Proposing {suffix}",
            owner_user_id=commissioner.id,
            owner_name="Stress Commissioner",
        )
        receiving_team = Team(
            league_id=league.id,
            name=f"Stress Transition Receiving {suffix}",
            owner_user_id=receiver.id,
            owner_name="Stress Receiver",
        )
        db.add_all([proposing_team, receiving_team])
        db.flush()

        accept_give = Player(name=f"Stress Accept QB {suffix}", school="Stress U", position="QB")
        accept_receive = Player(name=f"Stress Accept RB {suffix}", school="Stress U", position="RB")
        veto_give = Player(name=f"Stress Veto WR {suffix}", school="Stress U", position="WR")
        veto_receive = Player(name=f"Stress Veto TE {suffix}", school="Stress U", position="TE")
        db.add_all([accept_give, accept_receive, veto_give, veto_receive])
        db.flush()
        db.add_all(
            [
                RosterEntry(league_id=league.id, team_id=proposing_team.id, player_id=accept_give.id, slot="QB", status="active"),
                RosterEntry(league_id=league.id, team_id=receiving_team.id, player_id=accept_receive.id, slot="RB", status="active"),
                RosterEntry(league_id=league.id, team_id=proposing_team.id, player_id=veto_give.id, slot="WR", status="active"),
                RosterEntry(league_id=league.id, team_id=receiving_team.id, player_id=veto_receive.id, slot="TE", status="active"),
            ]
        )

        accept_cancel_offer = TradeOffer(
            league_id=league.id,
            proposing_team_id=proposing_team.id,
            receiving_team_id=receiving_team.id,
            created_by_user_id=commissioner.id,
            status="proposed",
            expires_at=now + timedelta(days=1),
        )
        worker_veto_offer = TradeOffer(
            league_id=league.id,
            proposing_team_id=proposing_team.id,
            receiving_team_id=receiving_team.id,
            created_by_user_id=commissioner.id,
            status="accepted_pending",
            accepted_at=now - timedelta(minutes=2),
            process_after=now - timedelta(minutes=1),
        )
        db.add_all([accept_cancel_offer, worker_veto_offer])
        db.flush()
        db.add_all(
            [
                TradeOfferItem(trade_offer_id=accept_cancel_offer.id, team_id=proposing_team.id, player_id=accept_give.id),
                TradeOfferItem(trade_offer_id=accept_cancel_offer.id, team_id=receiving_team.id, player_id=accept_receive.id),
                TradeOfferItem(trade_offer_id=worker_veto_offer.id, team_id=proposing_team.id, player_id=veto_give.id),
                TradeOfferItem(trade_offer_id=worker_veto_offer.id, team_id=receiving_team.id, player_id=veto_receive.id),
            ]
        )
        db.commit()
        return {
            "league_id": league.id,
            "commissioner_id": commissioner.id,
            "receiver_id": receiver.id,
            "proposing_team_id": proposing_team.id,
            "receiving_team_id": receiving_team.id,
            "accept_give_id": accept_give.id,
            "accept_receive_id": accept_receive.id,
            "accept_cancel_offer_id": accept_cancel_offer.id,
            "worker_veto_offer_id": worker_veto_offer.id,
            "now": now,
        }


def _run_trade_action(start: threading.Barrier, seed: dict[str, int | datetime], action: str) -> str:
    start.wait(timeout=15)
    try:
        with SessionLocal() as db:
            league = db.get(League, seed["league_id"])
            if action == "accept":
                receiver = db.get(User, seed["receiver_id"])
                accept_trade_offer(db, league, seed["accept_cancel_offer_id"], receiver, TradeActionRequest())
            elif action == "cancel":
                commissioner = db.get(User, seed["commissioner_id"])
                cancel_trade_offer(db, league, seed["accept_cancel_offer_id"], commissioner, TradeActionRequest())
            elif action == "veto":
                commissioner = db.get(User, seed["commissioner_id"])
                commissioner_veto_trade(db, league, seed["worker_veto_offer_id"], commissioner, TradeActionRequest())
            elif action == "process":
                process_trade_offers_once(db, now=seed["now"])
            else:
                raise ValueError(f"unknown trade stress action: {action}")
        return "success"
    except HTTPException as exc:
        return f"http_{exc.status_code}"


def _assert_trade_transition_races(seed: dict[str, int | datetime], results: dict[str, str]) -> dict[str, str]:
    with SessionLocal() as db:
        accept_cancel = db.get(TradeOffer, seed["accept_cancel_offer_id"])
        worker_veto = db.get(TradeOffer, seed["worker_veto_offer_id"])
        accept_give_owner = db.query(RosterEntry.team_id).filter_by(
            league_id=seed["league_id"], player_id=seed["accept_give_id"]
        ).scalar()
        accept_receive_owner = db.query(RosterEntry.team_id).filter_by(
            league_id=seed["league_id"], player_id=seed["accept_receive_id"]
        ).scalar()

    assert accept_cancel is not None and accept_cancel.status in {"processed", "cancelled", "accepted_pending"}, (
        f"accept-vs-cancel did not select one authoritative state: {accept_cancel.status if accept_cancel else None}; results={results}"
    )
    if accept_cancel.status == "processed":
        assert accept_give_owner == seed["receiving_team_id"]
        assert accept_receive_owner == seed["proposing_team_id"]
    else:
        assert accept_give_owner == seed["proposing_team_id"]
        assert accept_receive_owner == seed["receiving_team_id"]
    assert worker_veto is not None and worker_veto.status in {"processed", "vetoed"}, (
        f"worker-vs-veto did not select one terminal state: {worker_veto.status if worker_veto else None}; results={results}"
    )
    return {
        "accept_vs_cancel": accept_cancel.status,
        "worker_vs_veto": worker_veto.status,
    }


def _run_trade_transition_races() -> dict[str, str]:
    seed = _seed_trade_transition_races()
    accept_cancel_start = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        accept_result, cancel_result = list(
            executor.map(
                lambda action: _run_trade_action(accept_cancel_start, seed, action),
                ["accept", "cancel"],
            )
        )

    worker_veto_start = threading.Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        process_result, veto_result = list(
            executor.map(
                lambda action: _run_trade_action(worker_veto_start, seed, action),
                ["process", "veto"],
            )
        )

    return _assert_trade_transition_races(
        seed,
        {
            "accept": accept_result,
            "cancel": cancel_result,
            "process": process_result,
            "veto": veto_result,
        },
    )


def _assert_scoring_rollback() -> dict[str, int]:
    """Prove a failed recalculation rolls back all partial score writes on Postgres."""

    suffix = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        user = User(
            email=f"stress-scoring-{suffix}@example.com",
            first_name="Stress Scoring",
            password_hash="not-used",
            api_token=f"stress-scoring-{suffix}",
            email_verified_at=now,
        )
        db.add(user)
        db.flush()
        league = League(
            name=f"Postgres scoring rollback stress {suffix}",
            season_year=2026,
            commissioner_user_id=user.id,
            max_teams=2,
        )
        db.add(league)
        db.flush()
        db.add(
            LeagueSettings(
                league_id=league.id,
                roster_slots_json={"QB": 1, "BENCH": 2},
                scoring_json={"pass_yards": 0.04},
                trade_review_type="none",
            )
        )
        team = Team(
            league_id=league.id,
            name=f"Stress Scoring Team {suffix}",
            owner_user_id=user.id,
            owner_name="Stress Scoring",
        )
        player = Player(name=f"Stress Scoring QB {suffix}", school="Stress U", position="QB")
        db.add_all([team, player])
        db.flush()
        db.add(
            RosterEntry(
                league_id=league.id,
                team_id=team.id,
                player_id=player.id,
                slot="QB",
                status="active",
            )
        )
        db.add(PlayerStat(player_id=player.id, season=2026, week=1, stats={"PassingYards": 250}))
        db.commit()

        original_recalculate_team_scores = scoring_service.recalculate_team_week_scores

        def fail_after_player_scores(*_args: object, **_kwargs: object) -> int:
            raise RuntimeError("intentional PostgreSQL scoring rollback stress failure")

        scoring_service.recalculate_team_week_scores = fail_after_player_scores
        try:
            try:
                run_league_scoring_recalculation(db, league.id, 2026, 1, provider="stress")
            except RuntimeError as exc:
                assert "intentional PostgreSQL scoring rollback" in str(exc)
            else:
                raise AssertionError("scoring rollback stress run unexpectedly succeeded")
        finally:
            scoring_service.recalculate_team_week_scores = original_recalculate_team_scores

        failed_run = db.query(ScoringRun).filter_by(league_id=league.id, status="failed").one()
        assert failed_run.error_message and "intentional PostgreSQL scoring rollback" in failed_run.error_message
        assert db.query(PlayerWeekScore).filter_by(league_id=league.id, season=2026, week=1).count() == 0
        assert db.query(TeamWeekScore).filter_by(league_id=league.id, season=2026, week=1).count() == 0
        return {"scoring_rollback_verified": 1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the lifecycle-worker locking stress test against PostgreSQL.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent worker sessions to launch.")
    args = parser.parse_args()
    workers = max(2, args.workers)
    seed = _seed_due_work()
    barrier = threading.Barrier(workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_run_worker, [barrier] * workers, [seed["process_at"]] * workers))
    lifecycle_summary = _assert_exactly_once(seed, results)
    lifecycle_summary.update(_run_trade_transition_races())
    lifecycle_summary.update(_assert_scoring_rollback())
    print(lifecycle_summary)


if __name__ == "__main__":
    main()
