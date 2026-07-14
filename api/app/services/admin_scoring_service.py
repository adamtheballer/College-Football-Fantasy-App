from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.provider_identity import UnmatchedProviderRow
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scoring_admin_audit import ScoringAdminAudit
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.admin_scoring import (
    AdminActionResponse,
    AdminCorrectionRequest,
    AdminRerunScoringRequest,
    AdminScoringAuditRead,
    CorrectionPreviewResponse,
    ProviderHealthRead,
    ProviderHealthResponse,
    ScoringSummaryRead,
)
from collegefootballfantasy_api.app.services.scoring_service import (
    calculate_player_fantasy_points,
    normalize_player_stats,
    recalculate_league_week_scores,
    run_league_scoring_recalculation,
)


def _summary_read(summary) -> ScoringSummaryRead:
    return ScoringSummaryRead(
        players_scored=summary.players_scored,
        teams_scored=summary.teams_scored,
        matchups_updated=summary.matchups_updated,
        standings_updated=summary.standings_updated,
    )


def _affected_league_ids_for_player(db: Session, player_id: int, season: int, week: int, league_id: int | None = None) -> list[int]:
    query = (
        db.query(RosterEntry.league_id)
        .join(League, League.id == RosterEntry.league_id)
        .filter(RosterEntry.player_id == player_id, League.season_year == season)
        .distinct()
    )
    if league_id is not None:
        query = query.filter(RosterEntry.league_id == league_id)
    league_ids = [row[0] for row in query.order_by(RosterEntry.league_id.asc()).all()]
    if league_id is not None and league_id not in league_ids and db.get(League, league_id):
        league_ids.append(league_id)
    return league_ids


def _current_player_stat(db: Session, player_id: int, season: int, week: int) -> PlayerStat | None:
    return (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id, PlayerStat.season == season, PlayerStat.week == week)
        .first()
    )


def preview_stat_correction(db: Session, payload: AdminCorrectionRequest) -> CorrectionPreviewResponse:
    player = db.get(Player, payload.player_id)
    if not player:
        raise LookupError("player not found")
    affected_league_ids = _affected_league_ids_for_player(db, payload.player_id, payload.season, payload.week)
    stat_row = _current_player_stat(db, payload.player_id, payload.season, payload.week)
    before_scores = {
        row.league_id: row.fantasy_points
        for row in db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.player_id == payload.player_id,
            PlayerWeekScore.season == payload.season,
            PlayerWeekScore.week == payload.week,
            PlayerWeekScore.league_id.in_(affected_league_ids or {0}),
        )
        .all()
    }
    projected_scores: dict[int, float] = {}
    normalized_stats = normalize_player_stats(payload.stats)
    for league_id in affected_league_ids:
        league = db.get(League, league_id)
        if not league:
            continue
        settings = db.query(LeagueSettings).filter_by(league_id=league_id).first()
        fantasy_points, _breakdown = calculate_player_fantasy_points(
            normalized_stats,
            settings.scoring_json if settings else {},
        )
        projected_scores[league_id] = fantasy_points
    return CorrectionPreviewResponse(
        player_id=payload.player_id,
        season=payload.season,
        week=payload.week,
        affected_league_ids=affected_league_ids,
        before_stats=stat_row.stats if stat_row else None,
        after_stats=payload.stats,
        before_scores={league_id: before_scores.get(league_id) for league_id in affected_league_ids},
        projected_scores=projected_scores,
    )


def _audit(
    db: Session,
    *,
    action: str,
    actor: User,
    reason: str,
    league_id: int | None = None,
    season: int | None = None,
    week: int | None = None,
    player_id: int | None = None,
    affected_league_ids: list[int] | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
) -> ScoringAdminAudit:
    row = ScoringAdminAudit(
        action=action,
        actor_user_id=actor.id,
        league_id=league_id,
        season=season,
        week=week,
        player_id=player_id,
        affected_league_ids=affected_league_ids,
        reason=reason,
        before_state=before_state,
        after_state=after_state,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def apply_stat_correction(db: Session, payload: AdminCorrectionRequest, actor: User) -> AdminActionResponse:
    preview = preview_stat_correction(db, payload)
    before_state = preview.model_dump(mode="json")
    stat_row = _current_player_stat(db, payload.player_id, payload.season, payload.week)
    if stat_row:
        stat_row.stats = payload.stats
    else:
        stat_row = PlayerStat(
            player_id=payload.player_id,
            season=payload.season,
            week=payload.week,
            source="admin_correction",
            stats=payload.stats,
        )
        db.add(stat_row)
        db.flush()
    summaries: dict[int, dict] = {}
    for league_id in preview.affected_league_ids:
        summary = recalculate_league_week_scores(db, league_id, payload.season, payload.week)
        summaries[league_id] = _summary_read(summary).model_dump()
    after_preview = preview_stat_correction(db, payload)
    audit = _audit(
        db,
        action="apply_stat_correction",
        actor=actor,
        reason=payload.reason,
        season=payload.season,
        week=payload.week,
        player_id=payload.player_id,
        affected_league_ids=preview.affected_league_ids,
        before_state=before_state,
        after_state={"preview": after_preview.model_dump(mode="json"), "summaries": summaries},
    )
    db.commit()
    db.refresh(audit)
    return AdminActionResponse(
        action="apply_stat_correction",
        status="success",
        message=f"Applied stat correction and recalculated {len(preview.affected_league_ids)} league(s).",
        audit=AdminScoringAuditRead.model_validate(audit),
        preview=after_preview,
    )


def rerun_scoring(db: Session, payload: AdminRerunScoringRequest, actor: User) -> AdminActionResponse:
    before_state = {"league_id": payload.league_id, "season": payload.season, "week": payload.week}
    try:
        summary = run_league_scoring_recalculation(
            db,
            league_id=payload.league_id,
            season=payload.season,
            week=payload.week,
            provider=payload.provider or "admin",
        )
    except Exception as exc:
        _audit(
            db,
            action="rerun_scoring_failed",
            actor=actor,
            reason=payload.reason,
            league_id=payload.league_id,
            season=payload.season,
            week=payload.week,
            before_state=before_state,
            after_state={"error": str(exc)},
        )
        db.commit()
        raise
    audit = _audit(
        db,
        action="rerun_scoring",
        actor=actor,
        reason=payload.reason,
        league_id=payload.league_id,
        season=payload.season,
        week=payload.week,
        before_state=before_state,
        after_state=_summary_read(summary).model_dump(),
    )
    db.commit()
    db.refresh(audit)
    return AdminActionResponse(
        action="rerun_scoring",
        status="success",
        message="Scoring recalculation completed.",
        audit=AdminScoringAuditRead.model_validate(audit),
        summary=_summary_read(summary),
    )


def reconcile_league_week(db: Session, league_id: int, season: int, week: int, reason: str, actor: User) -> AdminActionResponse:
    league = db.get(League, league_id)
    if not league:
        raise LookupError("league not found")
    summary = recalculate_league_week_scores(db, league_id, season, week)
    audit = _audit(
        db,
        action="reconcile_league_week",
        actor=actor,
        reason=reason,
        league_id=league_id,
        season=season,
        week=week,
        after_state=_summary_read(summary).model_dump(),
    )
    db.commit()
    db.refresh(audit)
    return AdminActionResponse(
        action="reconcile_league_week",
        status="success",
        message="League/week reconciliation completed.",
        audit=AdminScoringAuditRead.model_validate(audit),
        summary=_summary_read(summary),
    )


def reconcile_player_week(db: Session, player_id: int, season: int, week: int, reason: str, actor: User, league_id: int | None = None) -> AdminActionResponse:
    if not db.get(Player, player_id):
        raise LookupError("player not found")
    affected = _affected_league_ids_for_player(db, player_id, season, week, league_id=league_id)
    summaries: dict[int, dict] = {}
    for affected_league_id in affected:
        summary = recalculate_league_week_scores(db, affected_league_id, season, week)
        summaries[affected_league_id] = _summary_read(summary).model_dump()
    audit = _audit(
        db,
        action="reconcile_player_week",
        actor=actor,
        reason=reason,
        league_id=league_id,
        season=season,
        week=week,
        player_id=player_id,
        affected_league_ids=affected,
        after_state={"summaries": summaries},
    )
    db.commit()
    db.refresh(audit)
    return AdminActionResponse(
        action="reconcile_player_week",
        status="success",
        message=f"Player/week reconciliation completed for {len(affected)} league(s).",
        audit=AdminScoringAuditRead.model_validate(audit),
    )


def set_week_status(db: Session, *, league_id: int, season: int, week: int, status: str, reason: str, actor: User) -> AdminActionResponse:
    matchups = db.query(Matchup).filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week).all()
    if not matchups:
        raise LookupError("matchups not found")
    before_state = {"matchups": [{"id": row.id, "status": row.status} for row in matchups]}
    for matchup in matchups:
        matchup.status = status
    audit = _audit(
        db,
        action=f"{status}_week",
        actor=actor,
        reason=reason,
        league_id=league_id,
        season=season,
        week=week,
        before_state=before_state,
        after_state={"matchups": [{"id": row.id, "status": row.status} for row in matchups]},
    )
    db.commit()
    db.refresh(audit)
    return AdminActionResponse(
        action=f"{status}_week",
        status="success",
        message=f"Week marked {status}.",
        audit=AdminScoringAuditRead.model_validate(audit),
    )


def provider_health(db: Session) -> ProviderHealthResponse:
    sync_states = db.query(ProviderSyncState).order_by(ProviderSyncState.updated_at.desc()).limit(100).all()
    open_unmatched = db.query(UnmatchedProviderRow).filter(UnmatchedProviderRow.status == "open").count()
    failed_runs = db.query(ScoringRun).filter(ScoringRun.status == "failed").count()
    return ProviderHealthResponse(
        sync_states=[ProviderHealthRead.model_validate(row) for row in sync_states],
        open_unmatched_rows=open_unmatched,
        failed_scoring_runs=failed_runs,
    )
