#!/usr/bin/env python
"""Create the verified Week 1 Saturday Pick 6 contest.

The script intentionally delegates validation to the contest service.  It will
stop rather than guess a kickoff, opponent, player identity, or position.
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.saturday_pick import SaturdayPickContestCreate
from collegefootballfantasy_api.app.services.saturday_pick_service import create_contest, publish_contest


WEEK_ONE_RB_NAMES = (
    "Kewan Lacy",
    "Ahmad Hardy",
    "Antwan Raymond",
    "LJ Martin",
    "Nate Sheppard",
    "Cam Cook",
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the Week 1 Saturday Pick 6 contest.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument(
        "--actor-email",
        required=True,
        help="Existing operator account recorded as the contest creator. This trusted bootstrap command is not a public admin API.",
    )
    parser.add_argument("--sponsor-name", default=None)
    parser.add_argument("--sponsor-logo-url", default=None)
    parser.add_argument("--sponsor-offer", default=None)
    parser.add_argument("--sponsor-code", default=None)
    parser.add_argument("--sponsor-url", default=None)
    parser.add_argument("--sponsor-terms", default=None)
    parser.add_argument("--apply", action="store_true", help="Persist only after the sealed schedule and six projections pass validation.")
    parser.add_argument("--publish", action="store_true", help="Publish only after all service validations succeed.")
    parser.add_argument("--database-url", default=settings.database_url)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.publish and not args.apply:
        raise SystemExit("--publish requires --apply.")
    ensure_models_registered()
    with Session(create_engine(args.database_url, pool_pre_ping=True)) as db:
        actor = db.query(User).filter(User.email == args.actor_email, User.is_active.is_(True)).one_or_none()
        if actor is None:
            raise SystemExit("An active operator matching --actor-email is required.")
        players = db.query(Player).filter(Player.name.in_(WEEK_ONE_RB_NAMES)).all()
        by_name = {player.name: player for player in players}
        missing = [name for name in WEEK_ONE_RB_NAMES if name not in by_name]
        if missing:
            raise SystemExit(f"Missing canonical player identities: {', '.join(missing)}")
        sponsor_fields = {}
        if settings.saturday_pick_6_sponsors_enabled:
            sponsor_fields = {
                "sponsor_name": args.sponsor_name,
                "sponsor_logo_url": args.sponsor_logo_url,
                "sponsor_offer_text": args.sponsor_offer,
                "sponsor_code": args.sponsor_code,
                "sponsor_url": args.sponsor_url,
                "sponsor_terms": args.sponsor_terms,
            }

        payload = SaturdayPickContestCreate(
            season=args.season,
            week_number=args.week,
            contest_position="RB",
            title="Saturday Pick 6",
            featured_player_ids=[by_name[name].id for name in WEEK_ONE_RB_NAMES],
            **sponsor_fields,
        )
        try:
            contest = create_contest(db, payload, actor)
            if args.publish:
                publish_contest(db, contest)
            contest_status = contest.status
            contest_id = contest.id
            if args.apply:
                db.commit()
            else:
                db.rollback()
        except ValueError as exc:
            db.rollback()
            raise SystemExit(f"Week 1 Saturday Pick 6 was not created: {exc}") from exc
        print({"mode": "apply" if args.apply else "dry-run", "contest_id": contest_id if args.apply else None, "status": contest_status, "players": list(WEEK_ONE_RB_NAMES)})


if __name__ == "__main__":
    main()
