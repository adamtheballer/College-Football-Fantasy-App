"""Shared authority for when a fantasy week is safe to publish as complete."""
from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.matchup import Matchup


FINAL_MATCHUP_STATUSES = frozenset({"final", "stat_corrected"})
MAX_REGULAR_SEASON_WEEK = 13


def week_is_authoritatively_finalized(db: Session, *, season: int, week: int) -> bool:
    """Return true only when every persisted app matchup for a week is final."""

    statuses = [
        str(status).casefold()
        for (status,) in db.query(Matchup.status)
        .filter(Matchup.season == season, Matchup.week == week)
        .all()
    ]
    return bool(statuses) and all(status in FINAL_MATCHUP_STATUSES for status in statuses)


def latest_authoritatively_finalized_week(db: Session, *, season: int) -> int:
    """Return the latest uninterrupted finalized fantasy week for ``season``."""

    completed_week = 0
    for week in range(1, MAX_REGULAR_SEASON_WEEK + 1):
        if not week_is_authoritatively_finalized(db, season=season, week=week):
            break
        completed_week = week
    return completed_week
