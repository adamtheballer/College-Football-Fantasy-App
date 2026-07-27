#!/usr/bin/env python
"""Backfill the immutable league-player ledger from persisted draft and transaction rows.

Run after migration: `PYTHONPATH=. uv run python scripts/backfill_league_player_history.py --league-id 1 --dry-run`.
The event-key uniqueness constraint makes `--apply` safe to repeat.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_player_event import LeaguePlayerEvent
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.services.league_player_history import (
    EVENT_AUTO_DRAFTED,
    EVENT_DRAFTED,
    EVENT_DROPPED,
    EVENT_FREE_AGENT_ADDED,
    EVENT_TRADED,
    EVENT_WAIVER_CLAIMED,
    append_league_player_event,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill league-specific player history.")
    parser.add_argument("--league-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true", help="Persist events. Without this flag the command is a dry run.")
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument("--report-dir", default="reports")
    return parser.parse_args()


def _event_type(transaction: Transaction) -> str | None:
    kind = transaction.transaction_type.lower()
    if kind.startswith("waiver_add"):
        return EVENT_WAIVER_CLAIMED
    if kind.startswith("free_agent") or kind in {"add", "add_drop"}:
        return EVENT_FREE_AGENT_ADDED
    if kind == "drop":
        return EVENT_DROPPED
    if kind == "trade_processed":
        return EVENT_TRADED
    return None


def main() -> int:
    args = parse_args()
    ensure_models_registered()
    engine = create_engine(args.database_url, pool_pre_ping=True)
    report_rows: list[dict[str, object]] = []
    counts: Counter[str] = Counter()
    with Session(engine) as db:
        league = db.get(League, args.league_id)
        if not league:
            raise SystemExit(f"league {args.league_id} not found")
        teams = {team.id: team for team in db.query(Team).filter(Team.league_id == league.id)}
        for pick in db.query(DraftPick).join(Draft, Draft.id == DraftPick.draft_id).filter(Draft.league_id == league.id):
            player = db.get(Player, pick.player_id)
            team = teams.get(pick.team_id)
            if not player or not team:
                continue
            key = f"draft-pick:{pick.id}"
            exists = db.query(LeaguePlayerEvent.id).filter(
                LeaguePlayerEvent.league_id == league.id,
                LeaguePlayerEvent.draft_pick_id == pick.id,
            ).first() is not None
            report_rows.append({"event_key": key, "event_type": EVENT_AUTO_DRAFTED if pick.auto_pick else EVENT_DRAFTED, "player_id": player.id, "action": "skipped" if exists else "would_create"})
            if not exists and args.apply:
                append_league_player_event(db, league=league, player=player, event_type=EVENT_AUTO_DRAFTED if pick.auto_pick else EVENT_DRAFTED, event_key=key, occurred_at=pick.created_at, fantasy_team=team, to_team=team, draft_id=pick.draft_id, draft_pick_id=pick.id, metadata={"round": pick.round_number, "pick_in_round": pick.round_pick, "overall_pick": pick.overall_pick, "auto_pick": pick.auto_pick})
            counts[report_rows[-1]["event_type"]] += int(not exists)
        claims = {claim.id: claim for claim in db.query(WaiverClaim).filter(WaiverClaim.league_id == league.id)}
        for transaction in db.query(Transaction).filter(Transaction.league_id == league.id).order_by(Transaction.id):
            event_type = _event_type(transaction)
            if not event_type or not transaction.player_id:
                continue
            player = db.get(Player, transaction.player_id)
            team = teams.get(transaction.team_id)
            if not player or not team:
                continue
            key = f"transaction:{transaction.id}:{transaction.player_id}:{event_type}"
            exists = db.query(LeaguePlayerEvent.id).filter(
                LeaguePlayerEvent.league_id == league.id,
                LeaguePlayerEvent.transaction_id == transaction.id,
                LeaguePlayerEvent.player_id == player.id,
                LeaguePlayerEvent.event_type == event_type,
            ).first() is not None
            report_rows.append({"event_key": key, "event_type": event_type, "player_id": player.id, "action": "skipped" if exists else "would_create"})
            claim = next((row for row in claims.values() if row.id and transaction.reason == f"waiver claim #{row.id}"), None)
            if not exists and args.apply:
                append_league_player_event(db, league=league, player=player, event_type=event_type, event_key=key, occurred_at=transaction.created_at, fantasy_team=team, to_team=team if event_type != EVENT_DROPPED else None, from_team=team if event_type == EVENT_DROPPED else None, transaction_id=transaction.id, waiver_claim_id=claim.id if claim else None, metadata={"related_player_id": transaction.related_player_id, "reason": transaction.reason})
            counts[event_type] += int(not exists)
        if args.apply:
            db.commit()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    with (report_dir / "player-history-backfill.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_key", "event_type", "player_id", "action"])
        writer.writeheader(); writer.writerows(report_rows)
    payload = {"league_id": args.league_id, "applied": args.apply, "event_counts": dict(counts), "rows": report_rows}
    (report_dir / "player-history-backfill.json").write_text(json.dumps(payload, indent=2) + "\n")
    (report_dir / "player-history-backfill.md").write_text("# Player history backfill\n\n" + f"League: {args.league_id}\n\nApplied: {args.apply}\n\n" + "| Event | New events |\n| --- | ---: |\n" + "".join(f"| {event} | {count} |\n" for event, count in sorted(counts.items())))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
