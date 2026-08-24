#!/usr/bin/env python3
"""Apply one auditable, provider-backed player availability correction.

This is an operator tool for a verified official/team injury update that has
not reached an automated availability provider yet.  It writes an Injury row
and a higher-priority CORRECTED_INJURY weekly projection, preserving the
underlying projection snapshots for auditability.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.player_news_event import PlayerNewsEvent
from collegefootballfantasy_api.app.services.availability_corrections import (
    CORRECTION_VERSION,
    MANUAL_VERIFIED_SOURCE,
    publish_zero_projection_for_unavailable_player,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("--school", required=True)
    parser.add_argument("--status", choices=("OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE"), required=True)
    parser.add_argument("--injury", required=True)
    parser.add_argument("--return-timeline", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--source-url", required=True, help="Public team or reputable local-report URL backing this correction.")
    parser.add_argument("--effective-until-week", type=int, help="Last week this override applies (defaults to --week).")
    parser.add_argument("--apply", action="store_true", help="Persist the correction; otherwise only print the target.")
    return parser.parse_args(argv)


def apply_correction(args: argparse.Namespace) -> dict[str, object]:
    ensure_models_registered()
    with SessionLocal() as db:
        player = db.scalar(
            select(Player).where(Player.name == args.player, Player.school == args.school)
        )
        if player is None:
            raise ValueError(f"No exact player match for {args.player} ({args.school}).")

        injury = db.scalar(
            select(Injury)
            .where(Injury.player_id == player.id, Injury.season == args.season, Injury.week == args.week)
            .order_by(Injury.updated_at.desc(), Injury.id.desc())
        )
        if injury is None:
            injury = Injury(player_id=player.id, season=args.season, week=args.week)
            db.add(injury)
        injury.status = args.status
        injury.injury = args.injury
        injury.return_timeline = args.return_timeline
        injury.practice_level = "DNP"
        injury.is_game_time_decision = False
        injury.is_returning = False
        injury.notes = args.notes
        effective_until_week = args.effective_until_week or args.week
        if effective_until_week < args.week:
            raise ValueError("--effective-until-week cannot be before --week.")
        content_hash = sha256(
            "\x1f".join((str(player.id), str(args.season), str(args.week), args.status, args.notes, args.source_url)).encode()
        ).hexdigest()
        event = db.scalar(
            select(PlayerAvailabilityEvent).where(
                PlayerAvailabilityEvent.player_id == player.id,
                PlayerAvailabilityEvent.season == args.season,
                PlayerAvailabilityEvent.week == args.week,
                PlayerAvailabilityEvent.source == MANUAL_VERIFIED_SOURCE,
            )
        )
        if event is None:
            event = PlayerAvailabilityEvent(player_id=player.id, season=args.season, week=args.week)
            db.add(event)
        event.status = args.status
        event.probability_active = 0.0 if args.status == "OUT" else 0.7
        event.availability_multiplier = 0.0 if args.status == "OUT" else 0.7
        event.source = MANUAL_VERIFIED_SOURCE
        event.source_url = args.source_url
        event.content_hash = content_hash
        event.source_reliability = 1.0
        event.published_at = datetime.now(timezone.utc)
        event.effective_from_week = args.week
        event.effective_until_week = effective_until_week
        event.reviewed = True
        event.notes = args.notes
        db.flush()
        news = db.scalar(
            select(PlayerNewsEvent).where(
                PlayerNewsEvent.player_id == player.id,
                PlayerNewsEvent.season == args.season,
                PlayerNewsEvent.week == args.week,
                PlayerNewsEvent.source == MANUAL_VERIFIED_SOURCE,
            )
        )
        if news is None:
            news = PlayerNewsEvent(player_id=player.id, season=args.season, week=args.week)
            db.add(news)
        news.event_type = "AVAILABILITY"
        news.source = MANUAL_VERIFIED_SOURCE
        news.source_url = args.source_url
        news.content_hash = content_hash
        news.source_reliability = 1.0
        news.published_at = event.published_at
        news.effective_from_week = args.week
        news.effective_until_week = effective_until_week
        news.reviewed = True
        news.notes = args.notes
        correction = publish_zero_projection_for_unavailable_player(
            db, player=player, season=args.season, week=args.week,
            status=args.status, note=args.notes,
        )
        if correction is None and args.status in {"OUT", "IR"}:
            raise ValueError(
                f"No published Week {args.week} projection exists for {args.player}; refusing to create an unverified correction."
            )

        result = {
            "player_id": player.id,
            "player": player.name,
            "school": player.school,
            "season": args.season,
            "week": args.week,
            "status": args.status,
            "projection_version": CORRECTION_VERSION,
            "fantasy_points": 0.0 if correction is not None else None,
            "source_url": args.source_url,
            "effective_until_week": effective_until_week,
        }
        if args.apply:
            db.commit()
            result["applied_at"] = datetime.now(timezone.utc).isoformat()
        else:
            db.rollback()
            result["preview"] = True
        return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(apply_correction(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
