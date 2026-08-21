"""Publish conservative post-final outlook snapshots from canonical weekly stats.

This service is called only after a fantasy week is scoring-certified final.
It never performs provider I/O and never uses an in-progress box score to
change a future projection or trade value.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.player_trade_value import calculate_weekly_trade_values
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections
from collegefootballfantasy_api.app.services.projections.usage import compute_usage_shares


POSTGAME_PROJECTION_VERSION = "MIDWEEK"
POSTGAME_MODEL_VERSION = "postgame_espn_v1"
FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}


def _week_is_certified_final(db: Session, *, season: int, week: int) -> bool:
    statuses = [
        str(status).casefold()
        for (status,) in db.query(Matchup.status)
        .filter(Matchup.season == season, Matchup.week == week)
        .all()
    ]
    return bool(statuses) and all(status in FINAL_MATCHUP_STATUSES for status in statuses)


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
    if completed_week < 1 or next_week > 13:
        return {"status": "not_applicable", "projected_week": next_week, "projections": 0, "values": 0}
    if not _week_is_certified_final(db, season=season, week=completed_week):
        return {"status": "waiting_for_finality", "projected_week": next_week, "projections": 0, "values": 0}

    schedules = db.query(TeamSchedule).filter(
        TeamSchedule.season == season,
        TeamSchedule.week == next_week,
    ).all()
    scheduled_teams = {row.team_name for row in schedules if not row.is_bye and row.opponent_name}
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
        candidate.baseline_games_played = completed_week
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
            setattr(current, column, getattr(candidate, column))

    # Week-one values remain CFB27-only until every Week 1 fantasy matchup is
    # certified final by the same lifecycle authority above.
    value_result = calculate_weekly_trade_values(
        db,
        season=season,
        week=completed_week,
    )
    db.flush()
    return {
        "status": "refreshed",
        "projected_week": next_week,
        "projections": len(projections),
        "values": int(value_result["calculated"]),
    }
