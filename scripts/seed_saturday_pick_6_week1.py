#!/usr/bin/env python
"""Create the verified Week 1 West Georgia Cornhole Saturday Pick 6 contest.

The script intentionally delegates validation to the contest service.  It will
stop rather than guess a kickoff, opponent, player identity, or position.
"""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
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

WEST_GEORGIA_CORNHOLE_LOGO_URL = "/west-georgia-cornhole.png"

# These four kickoff times were absent from the initial spreadsheet import.
# They come from the linked official athletic-department schedules and are kept
# here only as a tightly scoped launch-data correction.  The seed refuses to
# overwrite a populated schedule row, change an opponent, or change a date.
# That prevents this bootstrap utility from becoming a second schedule source.
WEEK_ONE_KICKOFF_CORRECTIONS = {
    "Missouri": {
        "opponent": "Arkansas-Pine Bluff",
        "game_date": "2026-09-03",
        "kickoff_at": "2026-09-04T00:00:00+00:00",  # 8:00 PM ET / 7:00 PM CT
        "tv_network": "SEC Network",
        "source_url": "https://uapblionsroar.com/sports/football/schedule/2026?grid=true",
    },
    "Rutgers": {
        "opponent": "Massachusetts",
        "game_date": "2026-09-03",
        "kickoff_at": "2026-09-03T22:00:00+00:00",  # 6:00 PM ET
        "tv_network": "Big Ten Network",
        "source_url": "https://scarletknights.com/news/2026/5/27/five-football-game-times-announced",
    },
    "BYU": {
        "opponent": "Utah Tech",
        "game_date": "2026-09-05",
        "kickoff_at": "2026-09-06T00:00:00+00:00",  # 6:00 PM MDT / 8:00 PM ET
        "tv_network": "ESPN+",
        "source_url": "https://byucougars.com/sports/football/schedule/season/2026",
    },
    "West Virginia": {
        "opponent": "Coastal Carolina",
        "game_date": "2026-09-05",
        "kickoff_at": "2026-09-05T16:00:00+00:00",  # noon ET
        "tv_network": "TNT/HBO Max",
        "source_url": "https://wvusports.com/news/2026/5/27/football-times-and-network-partners-announced-for-first-three-games",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the Week 1 Saturday Pick 6 sponsor contest.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument(
        "--actor-email",
        required=True,
        help="Existing operator account recorded as the contest creator. This trusted bootstrap command is not a public admin API.",
    )
    parser.add_argument("--sponsor-offer", default=None)
    parser.add_argument("--sponsor-code", default=None)
    parser.add_argument("--sponsor-url", default=None)
    parser.add_argument("--sponsor-terms", default=None)
    parser.add_argument("--publish", action="store_true", help="Publish only after all service validations succeed.")
    parser.add_argument("--database-url", default=settings.database_url)
    return parser.parse_args()


def backfill_missing_week_one_kickoffs(db: Session, *, season: int, week: int) -> None:
    """Fill only documented missing kickoff times for the fixed Week 1 lineup."""
    for school, correction in WEEK_ONE_KICKOFF_CORRECTIONS.items():
        schedule = (
            db.query(TeamSchedule)
            .filter(TeamSchedule.team_name == school, TeamSchedule.season == season, TeamSchedule.week == week)
            .one_or_none()
        )
        if schedule is None:
            raise ValueError(f"{school} is missing its canonical Week {week} schedule row.")
        if (
            schedule.opponent_name != correction["opponent"]
            or schedule.game_date is None
            or schedule.game_date.isoformat() != correction["game_date"]
        ):
            raise ValueError(f"{school} Week {week} schedule no longer matches the verified launch correction.")
        if schedule.kickoff_at is not None:
            continue
        schedule.kickoff_at = datetime.fromisoformat(correction["kickoff_at"])
        schedule.tv_network = correction["tv_network"]
        schedule.primary_source_url = correction["source_url"]


def main() -> None:
    args = parse_args()
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
        payload = SaturdayPickContestCreate(
            season=args.season,
            week_number=args.week,
            contest_position="RB",
            title="Saturday Pick 6",
            featured_player_ids=[by_name[name].id for name in WEEK_ONE_RB_NAMES],
            sponsor_name="West Georgia Cornhole",
            sponsor_logo_url=WEST_GEORGIA_CORNHOLE_LOGO_URL,
            sponsor_offer_text=args.sponsor_offer,
            sponsor_code=args.sponsor_code,
            sponsor_url=args.sponsor_url,
            sponsor_terms=args.sponsor_terms,
        )
        try:
            backfill_missing_week_one_kickoffs(db, season=args.season, week=args.week)
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
