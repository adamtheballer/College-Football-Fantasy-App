from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scoring_correction_audit import ScoringCorrectionAudit
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.domain.matchup_state import FINAL_MATCHUP_STATUSES, STAT_CORRECTED
from collegefootballfantasy_api.app.domain.scoring_engine import (
    CALCULATION_VERSION,
    NON_SCORING_SLOTS,
    calculate_player_fantasy_points,
    is_starting_slot,
    normalize_player_stats,
)
from collegefootballfantasy_api.app.services.lineup_locking import create_or_refresh_lineup_snapshots
from collegefootballfantasy_api.app.services.matchup_finalization import (
    finalize_league_week_matchups,
    mark_league_week_pending_final,
)
from collegefootballfantasy_api.app.services.matchup_scoring import update_matchup_scores_from_team_scores
from collegefootballfantasy_api.app.services.standings_recalc import recalculate_standings_for_week


@dataclass(frozen=True)
class ScoringSummary:
    players_scored: int
    teams_scored: int
    matchups_updated: int
    standings_updated: int


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _league_settings(db: Session, league_id: int) -> LeagueSettings | None:
    return db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()


def _stat_map(db: Session, season: int, week: int, player_ids: set[int]) -> dict[int, PlayerStat]:
    if not player_ids:
        return {}
    rows = (
        db.query(PlayerStat)
        .filter(
            PlayerStat.season == season,
            PlayerStat.week == week,
            PlayerStat.player_id.in_(player_ids),
        )
        .all()
    )
    return {row.player_id: row for row in rows}


def _source_event_id(stat_row: PlayerStat | None) -> str | None:
    if not stat_row or not isinstance(stat_row.stats, dict):
        return None
    for key in ("GameKey", "GameId", "EventId", "event_id", "game_id"):
        value = stat_row.stats.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _scoring_player_ids(db: Session, league_id: int, season: int, week: int) -> set[int]:
    rostered_ids = {
        row[0]
        for row in db.query(RosterEntry.player_id)
        .filter(RosterEntry.league_id == league_id)
        .distinct()
        .all()
    }
    matchup_team_ids: set[int] = set()
    for home_team_id, away_team_id in (
        db.query(Matchup.home_team_id, Matchup.away_team_id)
        .filter(
            Matchup.league_id == league_id,
            Matchup.season == season,
            Matchup.week == week,
        )
        .all()
    ):
        if home_team_id is not None:
            matchup_team_ids.add(home_team_id)
        if away_team_id is not None:
            matchup_team_ids.add(away_team_id)
    active_matchup_ids = {
        row[0]
        for row in db.query(RosterEntry.player_id)
        .filter(
            RosterEntry.league_id == league_id,
            RosterEntry.team_id.in_(matchup_team_ids or {0}),
        )
        .distinct()
        .all()
    }
    stat_ids = {
        row[0]
        for row in db.query(PlayerStat.player_id)
        .filter(PlayerStat.season == season, PlayerStat.week == week)
        .distinct()
        .all()
    }
    return rostered_ids | active_matchup_ids | stat_ids


def _score_payload_changed(
    score: PlayerWeekScore,
    *,
    fantasy_points: float,
    breakdown: dict,
    source_stat_id: int | None,
    source_provider: str | None,
    source_event_id: str | None,
) -> bool:
    return (
        float(score.fantasy_points or 0.0) != float(fantasy_points)
        or (score.breakdown_json or {}) != breakdown
        or score.source_stat_id != source_stat_id
        or score.source_provider != source_provider
        or score.source_event_id != source_event_id
    )


def recalculate_player_week_scores(db: Session, league_id: int, season: int, week: int) -> int:
    settings = _league_settings(db, league_id)
    scoring_rules = settings.scoring_json if settings else {}
    player_ids = _scoring_player_ids(db, league_id, season, week)
    if not player_ids:
        return 0
    players = db.query(Player).filter(Player.id.in_(player_ids)).order_by(Player.id.asc()).all()
    player_ids = {player.id for player in players}
    stat_by_player = _stat_map(db, season, week, player_ids)
    calculated_at = _now()
    scored = 0
    for player in players:
        stat_row = stat_by_player.get(player.id)
        normalized_stats = normalize_player_stats(stat_row.stats if stat_row else {}, player.position)
        fantasy_points, breakdown = calculate_player_fantasy_points(
            normalized_stats,
            scoring_rules,
            player.position,
        )
        score = (
            db.query(PlayerWeekScore)
            .filter(
                PlayerWeekScore.league_id == league_id,
                PlayerWeekScore.player_id == player.id,
                PlayerWeekScore.season == season,
                PlayerWeekScore.week == week,
            )
            .first()
        )
        if not score:
            score = PlayerWeekScore(
                league_id=league_id,
                player_id=player.id,
                season=season,
                week=week,
                stat_version=1,
            )
            db.add(score)
            score.previous_score = None
            score.correction_delta = 0.0
        else:
            changed = _score_payload_changed(
                score,
                fantasy_points=fantasy_points,
                breakdown=breakdown,
                source_stat_id=stat_row.id if stat_row else None,
                source_provider=stat_row.source if stat_row else None,
                source_event_id=_source_event_id(stat_row),
            )
            if changed:
                previous_score = float(score.fantasy_points or 0.0)
                score.previous_score = previous_score
                score.correction_delta = round(float(fantasy_points) - previous_score, 2)
                score.stat_version = int(score.stat_version or 1) + 1
        score.fantasy_points = fantasy_points
        score.breakdown_json = breakdown
        score.source_stat_id = stat_row.id if stat_row else None
        score.source_provider = stat_row.source if stat_row else None
        score.source_event_id = _source_event_id(stat_row)
        score.source_updated_at = stat_row.updated_at if stat_row else None
        score.calculation_version = CALCULATION_VERSION
        score.calculated_at = calculated_at
        scored += 1
    if scored:
        db.flush()
    return scored


def recalculate_team_week_score(db: Session, league_id: int, team_id: int, season: int, week: int) -> TeamWeekScore:
    snapshots = (
        db.query(LineupWeekSnapshot)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.team_id == team_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .all()
    )
    score_by_player = {
        row.player_id: row
        for row in db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
            PlayerWeekScore.player_id.in_({snapshot.player_id for snapshot in snapshots} or {0}),
        )
        .all()
    }
    starter_points = 0.0
    bench_points = 0.0
    player_breakdown = []
    for snapshot in snapshots:
        score = score_by_player.get(snapshot.player_id)
        points = float(score.fantasy_points if score else 0.0)
        slot = (snapshot.slot or "").upper()
        if snapshot.is_starter:
            starter_points += points
        elif slot not in NON_SCORING_SLOTS:
            bench_points += points
        player_breakdown.append(
            {
                "player_id": snapshot.player_id,
                "slot": slot,
                "is_starter": snapshot.is_starter,
                "points": round(points, 2),
            }
        )
    team_score = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league_id,
            TeamWeekScore.team_id == team_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
        .first()
    )
    if not team_score:
        team_score = TeamWeekScore(
            league_id=league_id,
            team_id=team_id,
            season=season,
            week=week,
        )
        db.add(team_score)
    team_score.starter_points = round(starter_points, 2)
    team_score.bench_points = round(bench_points, 2)
    team_score.total_points = round(starter_points, 2)
    team_score.points_starters = team_score.starter_points
    team_score.points_bench = team_score.bench_points
    team_score.points_total = team_score.total_points
    team_score.breakdown_json = {
        "players": player_breakdown,
        "starter_points": team_score.starter_points,
        "bench_points": team_score.bench_points,
        "total_points": team_score.total_points,
    }
    team_score.status = "live"
    team_score.calculated_at = _now()
    db.flush()
    return team_score


def recalculate_team_week_scores(db: Session, league_id: int, season: int, week: int) -> int:
    team_ids = [
        team_id
        for (team_id,) in db.query(Team.id)
        .filter(Team.league_id == league_id)
        .order_by(Team.id.asc())
        .all()
    ]
    for team_id in team_ids:
        recalculate_team_week_score(db, league_id, team_id, season, week)
    return len(team_ids)


def recalculate_matchup_scores(db: Session, league_id: int, season: int, week: int) -> int:
    return update_matchup_scores_from_team_scores(
        db,
        league_id,
        season,
        week,
        status="live",
        reason="live_score_update",
        mutate_finalized=False,
    )


def recalculate_league_week_scores(db: Session, league_id: int, season: int, week: int) -> ScoringSummary:
    create_or_refresh_lineup_snapshots(db, league_id, season, week)
    players_scored = recalculate_player_week_scores(db, league_id, season, week)
    teams_scored = recalculate_team_week_scores(db, league_id, season, week)
    matchups_updated = recalculate_matchup_scores(db, league_id, season, week)
    standings_updated = recalculate_standings_for_week(db, league_id, season, week)
    return ScoringSummary(
        players_scored=players_scored,
        teams_scored=teams_scored,
        matchups_updated=matchups_updated,
        standings_updated=standings_updated,
    )


def _matchup_status_snapshot(db: Session, league_id: int, season: int, week: int) -> dict[str, str]:
    rows = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week)
        .order_by(Matchup.id.asc())
        .all()
    )
    return {str(row.id): row.status for row in rows}


def finalize_league_week_scores(db: Session, league_id: int, season: int, week: int) -> ScoringSummary:
    summary = recalculate_league_week_scores(db, league_id, season, week)
    pending_updated = mark_league_week_pending_final(db, league_id, season, week)
    finalized_updated = finalize_league_week_matchups(db, league_id, season, week)
    standings_updated = recalculate_standings_for_week(db, league_id, season, week)
    db.flush()
    return ScoringSummary(
        players_scored=summary.players_scored,
        teams_scored=summary.teams_scored,
        matchups_updated=max(summary.matchups_updated, pending_updated, finalized_updated),
        standings_updated=standings_updated,
    )


def apply_stat_correction(
    db: Session,
    *,
    league_id: int,
    season: int,
    week: int,
    player_id: int,
    corrected_stats: dict,
    reason: str | None = None,
    created_by_user_id: int | None = None,
    source: str = "manual_correction",
) -> ScoringCorrectionAudit:
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
    old_points = float(old_score.fantasy_points if old_score else 0.0)
    old_statuses = _matchup_status_snapshot(db, league_id, season, week)
    stat = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id, PlayerStat.season == season, PlayerStat.week == week)
        .first()
    )
    old_raw = dict(stat.stats or {}) if stat else {}
    if not stat:
        stat = PlayerStat(player_id=player_id, season=season, week=week, source=source, stats=corrected_stats)
        db.add(stat)
        db.flush()
    else:
        stat.source = source
        stat.stats = corrected_stats
        db.flush()

    affected_league_ids = [
        row[0]
        for row in db.query(RosterEntry.league_id)
        .join(League, League.id == RosterEntry.league_id)
        .filter(
            RosterEntry.player_id == player_id,
            League.season_year == season,
        )
        .distinct()
        .all()
    ]
    if league_id not in affected_league_ids:
        affected_league_ids.append(league_id)
    for affected_league_id in sorted(affected_league_ids):
        recalculate_league_week_scores(db, affected_league_id, season, week)
        update_matchup_scores_from_team_scores(
            db,
            affected_league_id,
            season,
            week,
            status=STAT_CORRECTED,
            reason="stat_correction",
            mutate_finalized=True,
            always_version=True,
        )
        team_scores = (
            db.query(TeamWeekScore)
            .filter(
                TeamWeekScore.league_id == affected_league_id,
                TeamWeekScore.season == season,
                TeamWeekScore.week == week,
            )
            .all()
        )
        for team_score in team_scores:
            team_score.status = STAT_CORRECTED
        recalculate_standings_for_week(db, affected_league_id, season, week)
    new_score = (
        db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.player_id == player_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
        )
        .one()
    )
    audit = ScoringCorrectionAudit(
        league_id=league_id,
        season=season,
        week=week,
        player_id=player_id,
        source_stat_id=stat.id,
        affected_league_ids=sorted(affected_league_ids),
        old_raw_json=old_raw,
        new_raw_json=corrected_stats,
        old_fantasy_points=old_points,
        new_fantasy_points=float(new_score.fantasy_points or 0.0),
        old_matchup_statuses=old_statuses,
        new_matchup_statuses=_matchup_status_snapshot(db, league_id, season, week),
        reason=reason,
        created_by_user_id=created_by_user_id,
    )
    db.add(audit)
    db.flush()
    return audit


def run_league_scoring_recalculation(
    db: Session,
    league_id: int | None,
    season: int,
    week: int,
    provider: str = "manual",
) -> ScoringSummary:
    from collegefootballfantasy_api.app.services.scoring_worker_service import (
        RetryPolicy,
        run_scoring_worker_once,
    )

    result = run_scoring_worker_once(
        db,
        provider=provider,
        season=season,
        week=week,
        league_id=league_id,
        sync_provider_stats=lambda: {"rows_seen": 0, "upserted": 0, "skipped": 0, "events": 0, "allow_empty": True},
        retry_policy=RetryPolicy(max_attempts=1, initial_backoff_seconds=0),
        worker_id=f"manual-recalc-{league_id or 'all'}-{season}-{week}",
        sleeper=lambda _seconds: None,
    )
    if result.status == "skipped":
        raise ValueError("scoring job already running for this league/week")
    return ScoringSummary(
        players_scored=result.players_updated,
        teams_scored=result.teams_updated,
        matchups_updated=result.matchups_updated,
        standings_updated=result.standings_updated,
    )
