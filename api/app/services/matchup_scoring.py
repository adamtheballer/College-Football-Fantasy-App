from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.matchup_state import LIVE, is_live_refresh_locked
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.matchup_score_version import MatchupScoreVersion
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _team_score_map(db: Session, league_id: int, season: int, week: int) -> dict[int, TeamWeekScore]:
    rows = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
        .all()
    )
    return {row.team_id: row for row in rows}


def latest_matchup_score_version(db: Session, matchup_id: int) -> MatchupScoreVersion | None:
    return (
        db.query(MatchupScoreVersion)
        .filter(MatchupScoreVersion.matchup_id == matchup_id)
        .order_by(MatchupScoreVersion.version.desc())
        .first()
    )


def record_matchup_score_version(
    db: Session,
    matchup: Matchup,
    *,
    reason: str,
    scoring_run_id: int | None = None,
) -> MatchupScoreVersion:
    home_score = round(float(matchup.home_score or 0.0), 2)
    away_score = round(float(matchup.away_score or 0.0), 2)
    latest = latest_matchup_score_version(db, matchup.id)
    if (
        latest
        and float(latest.home_score or 0.0) == home_score
        and float(latest.away_score or 0.0) == away_score
        and latest.reason == reason
        and latest.scoring_run_id == scoring_run_id
    ):
        return latest
    next_version = int(latest.version if latest else 0) + 1
    version = MatchupScoreVersion(
        matchup_id=matchup.id,
        version=next_version,
        home_score=home_score,
        away_score=away_score,
        reason=reason,
        scoring_run_id=scoring_run_id,
        created_at=_now(),
    )
    db.add(version)
    db.flush()
    return version


def update_matchup_scores_from_team_scores(
    db: Session,
    league_id: int,
    season: int,
    week: int,
    *,
    status: str = LIVE,
    reason: str = "live_score_update",
    scoring_run_id: int | None = None,
    mutate_finalized: bool = False,
    always_version: bool = False,
) -> int:
    score_by_team = _team_score_map(db, league_id, season, week)
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week)
        .order_by(Matchup.id.asc())
        .all()
    )
    updated = 0
    for matchup in matchups:
        if is_live_refresh_locked(matchup.status) and not mutate_finalized:
            continue
        old_home = round(float(matchup.home_score or 0.0), 2)
        old_away = round(float(matchup.away_score or 0.0), 2)
        old_status = matchup.status
        home_score = score_by_team.get(matchup.home_team_id)
        away_score = score_by_team.get(matchup.away_team_id)
        matchup.home_score = round(float(home_score.total_points if home_score else 0.0), 2)
        matchup.away_score = round(float(away_score.total_points if away_score else 0.0), 2)
        matchup.status = status
        score_changed = old_home != matchup.home_score or old_away != matchup.away_score
        status_changed = old_status != status
        has_versions = (
            db.query(func.count(MatchupScoreVersion.id))
            .filter(MatchupScoreVersion.matchup_id == matchup.id)
            .scalar()
            or 0
        ) > 0
        if score_changed or status_changed or always_version or not has_versions:
            record_matchup_score_version(db, matchup, reason=reason, scoring_run_id=scoring_run_id)
        updated += 1
    if updated:
        db.flush()
    return updated
