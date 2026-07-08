from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.provider_player_identity_audit import ProviderPlayerIdentityAudit
from collegefootballfantasy_api.app.models.provider_unmatched_player_row import ProviderUnmatchedPlayerRow
from collegefootballfantasy_api.app.models.scoring_correction_audit import ScoringCorrectionAudit
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.provider_identity_audit import (
    duplicate_name_school_pairs,
    players_missing_provider_ids,
)
from collegefootballfantasy_api.app.services.scoring_service import apply_stat_correction, finalize_league_week_scores

router = APIRouter()


def _scoring_run_row(run: ScoringRun) -> dict:
    return {
        "id": run.id,
        "league_id": run.league_id,
        "season": run.season,
        "week": run.week,
        "provider": run.provider,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "players_updated": run.players_updated,
        "teams_updated": run.teams_updated,
        "matchups_updated": run.matchups_updated,
        "provider_latency_ms": run.provider_latency_ms,
        "rows_fetched": run.rows_fetched,
        "rows_matched": run.rows_matched,
        "rows_unmatched": run.rows_unmatched,
        "provider_events_seen": run.provider_events_seen,
        "retry_count": run.retry_count,
        "data_age_seconds": run.data_age_seconds,
        "lock_key": run.lock_key,
        "worker_id": run.worker_id,
        "last_successful_run_id": run.last_successful_run_id,
        "error_message": run.error_message,
    }


@router.get("/runs")
def list_scoring_runs(
    league_id: int | None = None,
    season: int | None = None,
    week: int | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    query = db.query(ScoringRun)
    if league_id is not None:
        query = query.filter(ScoringRun.league_id == league_id)
    if season is not None:
        query = query.filter(ScoringRun.season == season)
    if week is not None:
        query = query.filter(ScoringRun.week == week)
    if status_filter:
        query = query.filter(ScoringRun.status == status_filter)
    rows = query.order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc()).limit(max(1, min(limit, 200))).all()
    return {"data": [_scoring_run_row(row) for row in rows]}


@router.get("/runs/{run_id}")
def get_scoring_run(
    run_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    run = db.get(ScoringRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scoring run not found")
    return _scoring_run_row(run)


@router.get("/leagues/{league_id}/weeks/{week}")
def league_week_reconciliation(
    league_id: int,
    week: int,
    season: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    runs = (
        db.query(ScoringRun)
        .filter(ScoringRun.league_id == league_id, ScoringRun.season == season, ScoringRun.week == week)
        .order_by(ScoringRun.started_at.desc(), ScoringRun.id.desc())
        .limit(10)
        .all()
    )
    player_scores = (
        db.query(PlayerWeekScore)
        .filter(PlayerWeekScore.league_id == league_id, PlayerWeekScore.season == season, PlayerWeekScore.week == week)
        .all()
    )
    team_scores = (
        db.query(TeamWeekScore)
        .filter(TeamWeekScore.league_id == league_id, TeamWeekScore.season == season, TeamWeekScore.week == week)
        .all()
    )
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week)
        .all()
    )
    corrections = (
        db.query(ScoringCorrectionAudit)
        .filter(
            ScoringCorrectionAudit.league_id == league_id,
            ScoringCorrectionAudit.season == season,
            ScoringCorrectionAudit.week == week,
        )
        .order_by(ScoringCorrectionAudit.created_at.desc(), ScoringCorrectionAudit.id.desc())
        .all()
    )
    return {
        "league_id": league_id,
        "season": season,
        "week": week,
        "runs": [_scoring_run_row(row) for row in runs],
        "player_scores": [
            {
                "player_id": row.player_id,
                "fantasy_points": row.fantasy_points,
                "breakdown_json": row.breakdown_json,
                "source_stat_id": row.source_stat_id,
                "stat_version": row.stat_version,
                "source_provider": row.source_provider,
                "source_event_id": row.source_event_id,
                "source_updated_at": row.source_updated_at,
                "calculation_version": row.calculation_version,
                "previous_score": row.previous_score,
                "correction_delta": row.correction_delta,
                "calculated_at": row.calculated_at,
            }
            for row in player_scores
        ],
        "team_scores": [
            {
                "team_id": row.team_id,
                "starter_points": row.starter_points,
                "bench_points": row.bench_points,
                "total_points": row.total_points,
                "status": row.status,
                "breakdown_json": row.breakdown_json,
                "calculated_at": row.calculated_at,
            }
            for row in team_scores
        ],
        "matchups": [
            {
                "matchup_id": row.id,
                "home_team_id": row.home_team_id,
                "away_team_id": row.away_team_id,
                "home_score": row.home_score,
                "away_score": row.away_score,
                "status": row.status,
            }
            for row in matchups
        ],
        "corrections": [
            {
                "id": row.id,
                "player_id": row.player_id,
                "source_stat_id": row.source_stat_id,
                "old_fantasy_points": row.old_fantasy_points,
                "new_fantasy_points": row.new_fantasy_points,
                "reason": row.reason,
                "created_by_user_id": row.created_by_user_id,
                "created_at": row.created_at,
            }
            for row in corrections
        ],
    }


@router.post("/leagues/{league_id}/weeks/{week}/finalize")
def finalize_league_week(
    league_id: int,
    week: int,
    season: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    summary = finalize_league_week_scores(db, league_id, season, week)
    db.commit()
    return {
        "league_id": league_id,
        "season": season,
        "week": week,
        "status": "final",
        "players_scored": summary.players_scored,
        "teams_scored": summary.teams_scored,
        "matchups_updated": summary.matchups_updated,
        "standings_updated": summary.standings_updated,
    }


@router.post("/leagues/{league_id}/weeks/{week}/stat-corrections")
def correct_player_stat(
    league_id: int,
    week: int,
    payload: dict,
    season: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
) -> dict:
    player_id = payload.get("player_id")
    corrected_stats = payload.get("stats")
    if not isinstance(player_id, int) or not isinstance(corrected_stats, dict):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="player_id and stats are required")
    audit = apply_stat_correction(
        db,
        league_id=league_id,
        season=season,
        week=week,
        player_id=player_id,
        corrected_stats=corrected_stats,
        reason=payload.get("reason"),
        created_by_user_id=admin.id,
    )
    db.commit()
    return {
        "id": audit.id,
        "league_id": audit.league_id,
        "season": audit.season,
        "week": audit.week,
        "player_id": audit.player_id,
        "source_stat_id": audit.source_stat_id,
        "old_fantasy_points": audit.old_fantasy_points,
        "new_fantasy_points": audit.new_fantasy_points,
        "status": "stat_corrected",
    }


@router.get("/players/{player_id}/weeks/{week}")
def player_week_reconciliation(
    player_id: int,
    week: int,
    season: int,
    league_id: int | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    stat = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id, PlayerStat.season == season, PlayerStat.week == week)
        .first()
    )
    score_query = db.query(PlayerWeekScore).filter(
        PlayerWeekScore.player_id == player_id,
        PlayerWeekScore.season == season,
        PlayerWeekScore.week == week,
    )
    if league_id is not None:
        score_query = score_query.filter(PlayerWeekScore.league_id == league_id)
    scores = score_query.all()
    return {
        "player_id": player_id,
        "season": season,
        "week": week,
        "raw_stat": {
            "id": stat.id,
            "source": stat.source,
            "stats": stat.stats,
            "updated_at": stat.updated_at,
        }
        if stat
        else None,
        "scores": [
            {
                "league_id": row.league_id,
                "fantasy_points": row.fantasy_points,
                "breakdown_json": row.breakdown_json,
                "source_stat_id": row.source_stat_id,
                "calculated_at": row.calculated_at,
            }
            for row in scores
        ],
    }


@router.get("/unmatched-provider-rows")
def list_unmatched_provider_rows(
    provider: str | None = None,
    season: int | None = None,
    week: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    query = db.query(ProviderUnmatchedPlayerRow)
    if provider:
        query = query.filter(ProviderUnmatchedPlayerRow.provider == provider)
    if season is not None:
        query = query.filter(ProviderUnmatchedPlayerRow.season == season)
    if week is not None:
        query = query.filter(ProviderUnmatchedPlayerRow.week == week)
    rows = query.order_by(ProviderUnmatchedPlayerRow.created_at.desc()).limit(max(1, min(limit, 500))).all()
    return {
        "data": [
            {
                "id": row.id,
                "provider": row.provider,
                "season": row.season,
                "week": row.week,
                "provider_player_id": row.provider_player_id,
                "provider_player_name": row.provider_player_name,
                "provider_team": row.provider_team,
                "reason": row.reason,
                "status": row.status,
                "raw_json": row.raw_json,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/provider-identity")
def provider_identity_report(
    provider: str | None = None,
    season: int | None = None,
    week: int | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    query = db.query(ProviderPlayerIdentityAudit)
    if provider:
        query = query.filter(ProviderPlayerIdentityAudit.provider == provider)
    if season is not None:
        query = query.filter(ProviderPlayerIdentityAudit.season == season)
    if week is not None:
        query = query.filter(ProviderPlayerIdentityAudit.week == week)
    audits = query.order_by(ProviderPlayerIdentityAudit.created_at.desc()).limit(500).all()
    return {
        "missing_provider_ids": players_missing_provider_ids(db),
        "duplicate_name_school_pairs": duplicate_name_school_pairs(db),
        "identity_audits": [
            {
                "id": row.id,
                "provider": row.provider,
                "season": row.season,
                "week": row.week,
                "player_id": row.player_id,
                "provider_player_id": row.provider_player_id,
                "provider_player_name": row.provider_player_name,
                "provider_team": row.provider_team,
                "match_type": row.match_type,
                "confidence": row.confidence,
                "created_at": row.created_at,
            }
            for row in audits
        ],
    }
