#!/usr/bin/env python
"""Create the verified Week 1 West Georgia Cornhole Saturday Pick 6 contest.

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
    parser = argparse.ArgumentParser(description="Seed the Week 1 Saturday Pick 6 sponsor contest.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument("--admin-email", required=True, help="Existing administrator responsible for the contest.")
    parser.add_argument("--sponsor-offer", default=None)
    parser.add_argument("--sponsor-code", default=None)
    parser.add_argument("--sponsor-url", default=None)
    parser.add_argument("--sponsor-terms", default=None)
    parser.add_argument("--publish", action="store_true", help="Publish only after all service validations succeed.")
    parser.add_argument("--database-url", default=settings.database_url)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_models_registered()
    with Session(create_engine(args.database_url, pool_pre_ping=True)) as db:
        actor = db.query(User).filter(User.email == args.admin_email, User.is_admin.is_(True)).one_or_none()
        if actor is None:
            raise SystemExit("A verified administrator matching --admin-email is required.")
        players = db.query(Player).filter(Player.name.in_(WEEK_ONE_RB_NAMES)).all()
        by_name = {player.name: player for player in players}
        missing = [name for name in WEEK_ONE_RB_NAMES if name not in by_name]
        if missing:
            raise SystemExit(f"Missing canonical player identities: {', '.join(missing)}")
        payload = SaturdayPickContestCreate(
            season=args.season,
            week_number=args.week,
            contest_position="RB",
            title="Saturday Pick 6",
            featured_player_ids=[by_name[name].id for name in WEEK_ONE_RB_NAMES],
            sponsor_name="West Georgia Cornhole",
            sponsor_offer_text=args.sponsor_offer,
            sponsor_code=args.sponsor_code,
            sponsor_url=args.sponsor_url,
            sponsor_terms=args.sponsor_terms,
        )
        try:
            contest = create_contest(db, payload, actor)
            if args.publish:
                publish_contest(db, contest)
            db.commit()
        except ValueError as exc:
            db.rollback()
            raise SystemExit(f"Week 1 Saturday Pick 6 was not created: {exc}") from exc
        print({"contest_id": contest.id, "status": contest.status, "players": list(WEEK_ONE_RB_NAMES)})


if __name__ == "__main__":
    main()
