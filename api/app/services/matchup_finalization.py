from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.matchup_state import FINAL, PENDING_FINAL
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.matchup_scoring import update_matchup_scores_from_team_scores


def mark_league_week_pending_final(db: Session, league_id: int, season: int, week: int) -> int:
    return update_matchup_scores_from_team_scores(
        db,
        league_id,
        season,
        week,
        status=PENDING_FINAL,
        reason="provider_games_final",
        mutate_finalized=True,
        always_version=True,
    )


def finalize_league_week_matchups(db: Session, league_id: int, season: int, week: int) -> int:
    updated = update_matchup_scores_from_team_scores(
        db,
        league_id,
        season,
        week,
        status=FINAL,
        reason="all_starters_final",
        mutate_finalized=True,
        always_version=True,
    )
    team_scores = (
        db.query(TeamWeekScore)
        .filter(TeamWeekScore.league_id == league_id, TeamWeekScore.season == season, TeamWeekScore.week == week)
        .all()
    )
    for team_score in team_scores:
        team_score.status = FINAL
    if team_scores:
        db.flush()
    return updated
