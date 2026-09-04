"""Publish conservative post-final outlook snapshots from canonical weekly stats.

This service is called only after a fantasy week is scoring-certified final.
It never performs provider I/O and never uses an in-progress box score to
change a future projection or trade value.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.player_trade_value import calculate_weekly_trade_values
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections
from collegefootballfantasy_api.app.services.projections.ranges import weighted_projection_outcomes
from collegefootballfantasy_api.app.services.projections.usage import compute_usage_shares
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points


POSTGAME_PROJECTION_VERSION = "MIDWEEK"
POSTGAME_MODEL_VERSION = "postgame_espn_v2"
FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}
PERFORMANCE_RESIDUAL_WEIGHT = 0.22
MAX_RESIDUAL_SHARE = 0.75
MAX_PROJECTION_ADJUSTMENT_SHARE = 0.30


def _verified_fantasy_points(stats: dict | None, *, position: str) -> float | None:
    if not stats:
        return None
    for key in ("fantasy_points", "fantasyPoints", "fpts"):
        value = stats.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return calculate_fantasy_points(stats, position=position)


def performance_residual_adjustment(
    *,
    actual_points: float | None,
    projected_points: float | None,
    next_week_baseline: float | None,
) -> float:
    """Return a conservative Week N result adjustment for Week N+1.

    The next-game matchup model remains the primary forecast.  A certified
    performance miss contributes 22% of its capped residual, so a 14-point
    shortfall moves the next projection by about three points rather than
    treating one outlier as a permanent new talent level.
    """

    if (
        actual_points is None
        or projected_points is None
        or next_week_baseline is None
        or projected_points <= 0
        or next_week_baseline <= 0
    ):
        return 0.0
    expected = max(4.0, float(projected_points))
    residual = float(actual_points) - expected
    capped_residual = max(
        -expected * MAX_RESIDUAL_SHARE,
        min(expected * MAX_RESIDUAL_SHARE, residual),
    )
    adjustment = capped_residual * PERFORMANCE_RESIDUAL_WEIGHT
    maximum_adjustment = float(next_week_baseline) * MAX_PROJECTION_ADJUSTMENT_SHARE
    return max(-maximum_adjustment, min(maximum_adjustment, adjustment))


def _apply_performance_residuals(
    *,
    projections: list[WeeklyProjection],
    players_by_id: dict[int, Player],
    actual_by_player_id: dict[int, float],
    prior_projection_by_player_id: dict[int, WeeklyProjection],
) -> None:
    """Apply certified performance residuals while keeping ranges coupled."""

    for candidate in projections:
        baseline = float(candidate.fantasy_points or 0.0)
        prior_projection = prior_projection_by_player_id.get(candidate.player_id)
        adjustment = performance_residual_adjustment(
            actual_points=actual_by_player_id.get(candidate.player_id),
            projected_points=prior_projection.fantasy_points if prior_projection else None,
            next_week_baseline=baseline,
        )
        if adjustment == 0.0:
            continue
        candidate.fantasy_points = round(max(0.0, baseline + adjustment), 2)
        player = players_by_id.get(candidate.player_id)
        outcome_range = weighted_projection_outcomes(
            candidate.fantasy_points,
            position=player.position if player else None,
            expected_opportunities=candidate.expected_plays,
            availability_multiplier=candidate.availability_multiplier,
        )
        candidate.floor = outcome_range.floor
        candidate.ceiling = outcome_range.ceiling
        candidate.boom_prob = outcome_range.boom_prob
        candidate.bust_prob = outcome_range.bust_prob


def _week_is_certified_final(db: Session, *, season: int, week: int) -> bool:
    statuses = [
        str(status).casefold()
        for (status,) in db.query(Matchup.status)
        .filter(Matchup.season == season, Matchup.week == week)
        .all()
    ]
    return bool(statuses) and all(status in FINAL_MATCHUP_STATUSES for status in statuses)


def _completed_week_zero_teams(db: Session, *, season: int) -> set[str]:
    """Return only teams with a verified final Week 0 player-game record.

    This is intentionally not a league-finality check. Week 0 may update a
    participating player's Week 1 outlook, but never creates or scores a
    fantasy matchup.
    """

    rows = db.query(TeamSchedule).filter(
        TeamSchedule.season == season,
        TeamSchedule.week == 0,
        TeamSchedule.is_bye.is_(False),
    ).all()
    game_ids = {row.game_id for row in rows if row.game_id is not None}
    final_game_ids = {
        row.game_id
        for row in db.query(PlayerGameStat).filter(
            PlayerGameStat.game_id.in_(game_ids or {-1}),
            PlayerGameStat.season == season,
            PlayerGameStat.week == 0,
            PlayerGameStat.source == "espn_final_boxscore",
        ).all()
    }
    return {row.team_name for row in rows if row.game_id in final_game_ids}


def refresh_post_final_outlook(
    db: Session,
    *,
    season: int,
    completed_week: int,
) -> dict[str, int | str]:
    """Refresh next-week model snapshots and values after an entire week is final.

    Existing higher-authority FINAL projections continue to win over these
    MIDWEEK recalibrations.  Re-running after a verified stat correction is
    intentional and idempotently replaces only this service's snapshot.
    """
    next_week = completed_week + 1
    if completed_week < 0 or next_week > 13:
        return {"status": "not_applicable", "projected_week": next_week, "projections": 0, "values": 0}
    week_zero_teams = _completed_week_zero_teams(db, season=season) if completed_week == 0 else set()
    if completed_week == 0 and not week_zero_teams:
        return {"status": "waiting_for_finality", "projected_week": next_week, "projections": 0, "values": 0}
    if completed_week > 0 and not _week_is_certified_final(db, season=season, week=completed_week):
        return {"status": "waiting_for_finality", "projected_week": next_week, "projections": 0, "values": 0}

    schedules = db.query(TeamSchedule).filter(
        TeamSchedule.season == season,
        TeamSchedule.week == next_week,
    ).all()
    scheduled_teams = {row.team_name for row in schedules if not row.is_bye and row.opponent_name}
    if completed_week == 0:
        scheduled_teams.intersection_update(week_zero_teams)
    if not scheduled_teams:
        return {"status": "waiting_for_schedule", "projected_week": next_week, "projections": 0, "values": 0}

    players = db.query(Player).filter(Player.school.in_(scheduled_teams)).all()
    stats_by_player = {
        row.player_id: row.stats
        for row in db.query(PlayerStat).filter(
            PlayerStat.season == season,
            PlayerStat.week == completed_week,
            PlayerStat.verified.is_(True),
        )
        .all()
    }
    prior_projection_by_player_id = {
        row.player_id: row
        for row in db.scalars(
            current_published_projections_query(
                season=season,
                week=completed_week,
                player_ids=tuple(player.id for player in players),
            )
        ).all()
    }
    actual_by_player_id = {
        player.id: points
        for player in players
        if (
            points := _verified_fantasy_points(
                stats_by_player.get(player.id),
                position=player.position,
            )
        ) is not None
    }
    usage_by_player = {
        row.player_id: row
        for row in compute_usage_shares(players, stats_by_player, season, next_week)
    }
    team_env_by_team = {
        row.team_name: row
        for row in db.query(TeamEnvironment).filter(
            TeamEnvironment.season == season,
            TeamEnvironment.week == next_week,
        )
        .all()
    }
    defense_by_team = {
        row.team_name: row
        for row in db.query(DefenseRating).filter(
            DefenseRating.season == season,
            DefenseRating.week == next_week,
        )
        .all()
    }
    injuries_by_player = {
        row.player_id: row
        for row in db.query(Injury).filter(
            Injury.season == season,
            Injury.week == next_week,
        )
        .all()
    }
    opponent_by_team = {
        row.team_name: row.opponent_name
        for row in schedules
        if not row.is_bye and row.opponent_name
    }
    projections = build_weekly_projections(
        players=players,
        team_env_by_team=team_env_by_team,
        usage_by_player=usage_by_player,
        defense_by_team=defense_by_team,
        player_stats=stats_by_player,
        injuries_by_player=injuries_by_player,
        opponent_by_team=opponent_by_team,
        season=season,
        week=next_week,
    )
    _apply_performance_residuals(
        projections=projections,
        players_by_id={player.id: player for player in players},
        actual_by_player_id=actual_by_player_id,
        prior_projection_by_player_id=prior_projection_by_player_id,
    )
    existing = {
        row.player_id: row
        for row in db.query(WeeklyProjection).filter(
            WeeklyProjection.season == season,
            WeeklyProjection.week == next_week,
            WeeklyProjection.projection_version == POSTGAME_PROJECTION_VERSION,
        )
        .all()
    }
    projection_columns = [
        column.name
        for column in WeeklyProjection.__table__.columns
        if column.name not in {"id", "created_at", "updated_at"}
    ]
    for candidate in projections:
        candidate.projection_version = POSTGAME_PROJECTION_VERSION
        candidate.model_version = POSTGAME_MODEL_VERSION
        candidate.is_published = True
        candidate.baseline_source = f"verified_week_{completed_week}_stats"
        candidate.baseline_games_played = max(1, completed_week)
        current = existing.get(candidate.player_id)
        if current is None:
            db.add(candidate)
            continue
        # A post-game correction can arrive after the next game has kicked
        # off.  Preserve that next game's locked projection rather than
        # retroactively changing a live scoring baseline.
        if current.locked_at is not None:
            continue
        for column in projection_columns:
            value = getattr(candidate, column)
            # The model intentionally omits inapplicable stat categories
            # (for example, kicker-only fields on a QB). Keep the database
            # default in place on an idempotent refresh instead of writing a
            # NULL into a non-nullable projection column.
            if value is not None:
                setattr(current, column, value)

    # Week 0 is player-data only. It must not change trade values tied to a
    # fantasy matchup period.
    value_result = (
        {"calculated": 0}
        if completed_week == 0
        else calculate_weekly_trade_values(db, season=season, week=completed_week)
    )
    db.flush()
    return {
        "status": "refreshed",
        "projected_week": next_week,
        "projections": len(projections),
        "values": int(value_result["calculated"]),
    }
