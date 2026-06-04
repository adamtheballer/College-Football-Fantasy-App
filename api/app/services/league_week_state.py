from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.app.models.league import League
from api.app.models.league_week_state import LeagueWeekState
from api.app.models.matchup import Matchup

LeagueWeekStatus = Literal["open", "locked", "finalized", "corrected"]
VALID_WEEK_STATUSES: tuple[LeagueWeekStatus, ...] = ("open", "locked", "finalized", "corrected")


def get_or_create_week_state(
    db: Session,
    *,
    league_id: int,
    season: int,
    week: int,
) -> LeagueWeekState:
    existing = (
        db.query(LeagueWeekState)
        .filter(
            LeagueWeekState.league_id == league_id,
            LeagueWeekState.season == season,
            LeagueWeekState.week == week,
        )
        .first()
    )
    if existing:
        return existing
    created = LeagueWeekState(
        league_id=league_id,
        season=season,
        week=week,
        status="open",
    )
    db.add(created)
    db.flush()
    return created


def resolve_current_league_week(db: Session, *, league: League) -> tuple[int, int]:
    season = int(league.season_year)
    live_or_scheduled = (
        db.query(func.min(Matchup.week))
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == season,
            Matchup.status.in_(("scheduled", "live")),
        )
        .scalar()
    )
    if live_or_scheduled is not None:
        return season, int(live_or_scheduled)

    latest_any = (
        db.query(func.max(Matchup.week))
        .filter(Matchup.league_id == league.id, Matchup.season == season)
        .scalar()
    )
    if latest_any is not None:
        return season, int(latest_any)
    return season, 1


def enforce_lineup_window_open(db: Session, *, league: League) -> LeagueWeekState:
    season, week = resolve_current_league_week(db, league=league)
    state_row = get_or_create_week_state(db, league_id=league.id, season=season, week=week)
    if state_row.status != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"lineups are locked for week {week} ({state_row.status})",
        )
    return state_row


def transition_week_state(
    *,
    state_row: LeagueWeekState,
    next_status: LeagueWeekStatus,
) -> LeagueWeekState:
    current = str(state_row.status).strip().lower()
    if current not in VALID_WEEK_STATUSES:
        current = "open"
    if next_status not in VALID_WEEK_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid week status")

    valid_transitions: dict[str, set[str]] = {
        "open": {"locked"},
        "locked": {"open", "finalized"},
        "finalized": {"corrected"},
        "corrected": {"corrected"},
    }
    if next_status == current:
        return state_row
    if next_status not in valid_transitions.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"invalid week status transition: {current} -> {next_status}",
        )

    now_utc = datetime.now(timezone.utc)
    state_row.status = next_status
    if next_status == "locked":
        state_row.locked_at = now_utc
    if next_status == "finalized":
        state_row.finalized_at = now_utc
    if next_status == "corrected":
        state_row.corrected_at = now_utc
    return state_row
