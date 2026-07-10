from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import require_admin_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points, normalize_player_stats
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.provider_player_identity_audit import ProviderPlayerIdentityAudit
from collegefootballfantasy_api.app.models.provider_unmatched_player_row import ProviderUnmatchedPlayerRow
from collegefootballfantasy_api.app.models.scoring_correction_audit import ScoringCorrectionAudit
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.admin_scoring import (
    FinalizeWeekRequest,
    ProviderRowMappingRequest,
    ScoringCorrectionRequest,
)
from collegefootballfantasy_api.app.services.provider_identity_audit import (
    duplicate_name_school_pairs,
    ignore_unmatched_provider_row,
    map_unmatched_provider_row,
    players_missing_provider_ids,
    resolve_unmatched_provider_row,
)
from collegefootballfantasy_api.app.services.scoring_service import (
    apply_stat_correction,
    finalize_league_week_scores,
    run_league_scoring_recalculation,
)
from collegefootballfantasy_api.app.services.team_provider_mapping import weekly_lock_readiness

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


def _correction_affects_league(row: ScoringCorrectionAudit, league_id: int) -> bool:
    affected_league_ids = row.affected_league_ids or []
    return row.league_id == league_id or league_id in affected_league_ids


def _correction_audit_row(row: ScoringCorrectionAudit) -> dict:
    return {
        "id": row.id,
        "league_id": row.league_id,
        "affected_league_ids": row.affected_league_ids or [row.league_id],
        "season": row.season,
        "week": row.week,
        "player_id": row.player_id,
        "source_stat_id": row.source_stat_id,
        "old_fantasy_points": row.old_fantasy_points,
        "new_fantasy_points": row.new_fantasy_points,
        "old_raw_json": row.old_raw_json,
        "new_raw_json": row.new_raw_json,
        "old_matchup_statuses": row.old_matchup_statuses,
        "new_matchup_statuses": row.new_matchup_statuses,
        "reason": row.reason,
        "created_by_user_id": row.created_by_user_id,
        "created_at": row.created_at,
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


@router.get("/lock-readiness")
def lock_readiness_report(
    season: int,
    week: int,
    league_id: int | None = None,
    provider: str = "sportsdata",
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    return weekly_lock_readiness(db, season=season, week=week, provider=provider, league_id=league_id).as_dict()


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
        .filter(ScoringCorrectionAudit.season == season, ScoringCorrectionAudit.week == week)
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
            _correction_audit_row(row)
            for row in corrections
            if _correction_affects_league(row, league_id)
        ],
    }


@router.post("/leagues/{league_id}/weeks/{week}/finalize")
def finalize_league_week(
    league_id: int,
    week: int,
    payload: FinalizeWeekRequest | None = Body(default=None),
    season: int | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    requested_season = payload.season if payload else season
    if requested_season is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="season is required")
    summary = finalize_league_week_scores(db, league_id, requested_season, week)
    db.commit()
    return {
        "league_id": league_id,
        "season": requested_season,
        "week": week,
        "status": "final",
        "players_scored": summary.players_scored,
        "teams_scored": summary.teams_scored,
        "matchups_updated": summary.matchups_updated,
        "standings_updated": summary.standings_updated,
    }


@router.post("/leagues/{league_id}/weeks/{week}/rerun")
def rerun_league_week_scoring(
    league_id: int,
    week: int,
    season: int,
    provider: str = "manual",
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    try:
        summary = run_league_scoring_recalculation(db, league_id, season, week, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    db.commit()
    return {
        "league_id": league_id,
        "season": season,
        "week": week,
        "provider": provider,
        "status": "rerun_complete",
        "players_scored": summary.players_scored,
        "teams_scored": summary.teams_scored,
        "matchups_updated": summary.matchups_updated,
        "standings_updated": summary.standings_updated,
    }


@router.post("/leagues/{league_id}/weeks/{week}/stat-corrections/preview")
def preview_player_stat_correction(
    league_id: int,
    week: int,
    season: int,
    payload: ScoringCorrectionRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    player_id = payload.player_id
    corrected_stats = payload.stats
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    scoring_rules = settings.scoring_json if settings else {}
    normalized_stats = normalize_player_stats(corrected_stats, player.position)
    new_points, breakdown = calculate_player_fantasy_points(normalized_stats, scoring_rules, player.position)
    old_score = (
        db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.player_id == player_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
        )
        .first()
    )
    current_stat = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id, PlayerStat.season == season, PlayerStat.week == week)
        .first()
    )
    old_points = float(old_score.fantasy_points if old_score else 0.0)
    return {
        "league_id": league_id,
        "season": season,
        "week": week,
        "player_id": player_id,
        "player_name": player.name,
        "position": player.position,
        "source_stat_id": current_stat.id if current_stat else None,
        "old_fantasy_points": old_points,
        "new_fantasy_points": float(new_points),
        "delta": round(float(new_points) - old_points, 2),
        "normalized_stats": normalized_stats,
        "breakdown": breakdown,
        "status": "preview",
    }


@router.post("/leagues/{league_id}/weeks/{week}/stat-corrections")
def correct_player_stat(
    league_id: int,
    week: int,
    season: int,
    payload: ScoringCorrectionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
) -> dict:
    audit = apply_stat_correction(
        db,
        league_id=league_id,
        season=season,
        week=week,
        player_id=payload.player_id,
        corrected_stats=payload.stats,
        reason=payload.reason,
        created_by_user_id=admin.id,
    )
    db.commit()
    return {
        "id": audit.id,
        "league_id": audit.league_id,
        "affected_league_ids": audit.affected_league_ids or [audit.league_id],
        "season": audit.season,
        "week": audit.week,
        "player_id": audit.player_id,
        "source_stat_id": audit.source_stat_id,
        "old_fantasy_points": audit.old_fantasy_points,
        "new_fantasy_points": audit.new_fantasy_points,
        "status": "stat_corrected",
    }


@router.get("/leagues/{league_id}/weeks/{week}/stat-corrections")
def list_stat_corrections(
    league_id: int,
    week: int,
    season: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin_user),
) -> dict:
    candidate_rows = (
        db.query(ScoringCorrectionAudit)
        .filter(ScoringCorrectionAudit.season == season, ScoringCorrectionAudit.week == week)
        .order_by(ScoringCorrectionAudit.created_at.desc(), ScoringCorrectionAudit.id.desc())
        .all()
    )
    rows = [row for row in candidate_rows if _correction_affects_league(row, league_id)][: max(1, min(limit, 500))]
    return {
        "data": [_correction_audit_row(row) for row in rows]
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
                "dedupe_hash": row.dedupe_hash,
                "status": row.status,
                "mapped_player_id": row.mapped_player_id,
                "resolved_by_user_id": row.resolved_by_user_id,
                "resolved_at": row.resolved_at,
                "raw_json": row.raw_json,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.post("/unmatched-provider-rows/{row_id}/map")
def map_provider_unmatched_row(
    row_id: int,
    payload: ProviderRowMappingRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
) -> dict:
    unmatched = db.get(ProviderUnmatchedPlayerRow, row_id)
    if not unmatched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unmatched provider row not found")
    try:
        mapped = map_unmatched_provider_row(
            db,
            unmatched=unmatched,
            player_id=payload.player_id,
            resolved_by_user_id=admin.id,
            match_confidence=payload.match_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.commit()
    return {
        "id": mapped.id,
        "provider": mapped.provider,
        "provider_player_id": mapped.provider_player_id,
        "status": mapped.status,
        "mapped_player_id": mapped.mapped_player_id,
        "resolved_by_user_id": mapped.resolved_by_user_id,
        "resolved_at": mapped.resolved_at,
    }


@router.post("/unmatched-provider-rows/{row_id}/ignore")
def ignore_provider_unmatched_row(
    row_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
) -> dict:
    unmatched = db.get(ProviderUnmatchedPlayerRow, row_id)
    if not unmatched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unmatched provider row not found")
    ignored = ignore_unmatched_provider_row(db, unmatched=unmatched, resolved_by_user_id=admin.id)
    db.commit()
    return {
        "id": ignored.id,
        "provider": ignored.provider,
        "provider_player_id": ignored.provider_player_id,
        "status": ignored.status,
        "mapped_player_id": ignored.mapped_player_id,
        "resolved_by_user_id": ignored.resolved_by_user_id,
        "resolved_at": ignored.resolved_at,
    }


@router.post("/unmatched-provider-rows/{row_id}/resolve")
def resolve_provider_unmatched_row(
    row_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin_user),
) -> dict:
    unmatched = db.get(ProviderUnmatchedPlayerRow, row_id)
    if not unmatched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unmatched provider row not found")
    resolved = resolve_unmatched_provider_row(db, unmatched=unmatched, resolved_by_user_id=admin.id)
    db.commit()
    return {
        "id": resolved.id,
        "provider": resolved.provider,
        "provider_player_id": resolved.provider_player_id,
        "status": resolved.status,
        "mapped_player_id": resolved.mapped_player_id,
        "resolved_by_user_id": resolved.resolved_by_user_id,
        "resolved_at": resolved.resolved_at,
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
