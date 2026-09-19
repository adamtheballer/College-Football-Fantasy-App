"""Backfill only verified ESPN player portraits.

This deliberately reuses the exact name + school + position resolver. It never
constructs ESPN asset URLs from a name or an id, and it never imports stats or
changes projections. Existing trusted ESPN identities require just one profile
request; unmapped players are persisted only after an exact identity match.
"""

from __future__ import annotations

import argparse
import time
from typing import NamedTuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.services.espn_player_lookup import (
    persist_espn_player_profile,
    resolve_espn_player_identity_and_profile,
)
from collegefootballfantasy_api.app.services.historical_stats import resolve_espn_player_id


class HeadshotBackfillResult(NamedTuple):
    scanned: int
    updated: int
    already_present: int
    matched: int
    unresolved: int
    failed: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill only exact, provider-supplied ESPN player headshots.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum players to inspect.")
    parser.add_argument("--rostered-only", action="store_true", help="Prioritize active fantasy roster players only.")
    parser.add_argument("--requests-per-second", type=float, default=None, help="Bound ESPN requests; defaults to configured rate.")
    parser.add_argument("--dry-run", action="store_true", help="Count rows without contacting ESPN or writing data.")
    return parser.parse_args()


def players_missing_headshots(db: Session, *, rostered_only: bool, limit: int | None) -> list[Player]:
    query = db.query(Player).filter(or_(Player.image_url.is_(None), Player.espn_headshot_url.is_(None)))
    if rostered_only:
        query = query.join(RosterEntry, RosterEntry.player_id == Player.id).distinct()
    query = query.order_by(Player.sheet_adp.asc().nullslast(), Player.id.asc())
    if limit is not None:
        query = query.limit(max(0, limit))
    return query.all()


def backfill_headshots(
    db: Session,
    players: list[Player],
    *,
    client: ESPNClient | None,
    dry_run: bool,
    delay_seconds: float,
) -> HeadshotBackfillResult:
    updated = already_present = matched = unresolved = failed = 0
    for player in players:
        if player.image_url and player.espn_headshot_url:
            already_present += 1
            continue
        if dry_run:
            continue
        try:
            provider_player_id = resolve_espn_player_id(db, player)
            if provider_player_id:
                profile_updated = persist_espn_player_profile(player, client.get_athlete_profile(provider_player_id))
                if profile_updated:
                    db.commit()
                    matched += 1
                else:
                    db.rollback()
            else:
                result = resolve_espn_player_identity_and_profile(db, player, client=client)
                if result.outcome == "matched":
                    matched += 1
                else:
                    unresolved += 1
            if player.image_url or player.espn_headshot_url:
                updated += 1
        except Exception as exc:  # Keep an incomplete provider response from blocking the next player.
            db.rollback()
            failed += 1
            print(f"Unable to backfill headshot for player {player.id} ({player.name}): {exc}")
        if delay_seconds:
            time.sleep(delay_seconds)
    return HeadshotBackfillResult(
        scanned=len(players),
        updated=updated,
        already_present=already_present,
        matched=matched,
        unresolved=unresolved,
        failed=failed,
    )


def main() -> int:
    args = parse_args()
    if not settings.player_headshots_enabled and not args.dry_run:
        print("PLAYER_HEADSHOTS_ENABLED must be true before writing licensed ESPN headshots.")
        return 2
    rate = args.requests_per_second if args.requests_per_second is not None else settings.espn_historical_stats_requests_per_second
    delay_seconds = 1 / max(rate, 0.1)
    db = SessionLocal()
    try:
        players = players_missing_headshots(db, rostered_only=args.rostered_only, limit=args.limit)
        result = backfill_headshots(
            db,
            players,
            client=None if args.dry_run else ESPNClient(),
            dry_run=args.dry_run,
            delay_seconds=delay_seconds,
        )
    finally:
        db.close()
    print(
        "ESPN headshot backfill: "
        f"{result.scanned} scanned, {result.updated} portraits written, {result.already_present} already present, "
        f"{result.matched} verified profiles, {result.unresolved} unresolved, {result.failed} failed."
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
