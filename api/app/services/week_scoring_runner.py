from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league_week_state import LeagueWeekState
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.services.league_week_state import get_or_create_week_state, transition_week_state
from collegefootballfantasy_api.app.services.scoring_engine import now_utc, recompute_week_scores
from collegefootballfantasy_api.app.services.standings_engine import build_standings_snapshot


@dataclass
class WeekScoringRunExecution:
    run_row: ScoringRun
    week_state: LeagueWeekState
    standings_count: int
    scoring_result: object


def execute_week_scoring_run(
    db: Session,
    *,
    league_id: int,
    season: int,
    week: int,
    source_mode: str,
    finalize_matchups: bool,
    finalize_week: bool,
    note: str | None,
    created_by_user_id: int | None,
) -> WeekScoringRunExecution:
    if finalize_week and not finalize_matchups:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="finalize_week requires finalize_matchups=true",
        )

    run_row = ScoringRun(
        league_id=league_id,
        season=season,
        week=week,
        source_mode=source_mode,
        status="running",
        finalize_matchups=finalize_matchups,
        finalized_week_state=finalize_week,
        started_at=now_utc(),
        created_by_user_id=created_by_user_id,
        note=note,
    )
    db.add(run_row)
    db.flush()

    try:
        scoring_result = recompute_week_scores(
            db,
            league_id=league_id,
            season=season,
            week=week,
            source_mode=source_mode,  # type: ignore[arg-type]
            finalize_matchups=finalize_matchups,
        )

        state_row = (
            db.query(LeagueWeekState)
            .filter(
                LeagueWeekState.league_id == league_id,
                LeagueWeekState.season == season,
                LeagueWeekState.week == week,
            )
            .with_for_update()
            .first()
        )
        if not state_row:
            state_row = get_or_create_week_state(db, league_id=league_id, season=season, week=week)

        standings_rows = []
        if finalize_week:
            if state_row.status == "open":
                transition_week_state(state_row=state_row, next_status="locked")
            if state_row.status == "locked":
                transition_week_state(state_row=state_row, next_status="finalized")
            elif state_row.status == "finalized":
                transition_week_state(state_row=state_row, next_status="corrected")
            elif state_row.status != "corrected":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"cannot finalize week from state {state_row.status}",
                )

            standings_rows = build_standings_snapshot(
                db,
                league_id=league_id,
                season=season,
                through_week=week,
            )

        run_row.status = "completed"
        run_row.completed_at = now_utc()
        run_row.finalized_week_state = state_row.status in {"finalized", "corrected"}
        db.add(state_row)
        db.add(run_row)
        db.flush()

        return WeekScoringRunExecution(
            run_row=run_row,
            week_state=state_row,
            standings_count=len(standings_rows),
            scoring_result=scoring_result,
        )
    except Exception:
        run_row.status = "failed"
        run_row.completed_at = now_utc()
        db.add(run_row)
        db.flush()
        raise
