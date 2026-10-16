"""Build player-card trajectories from canonical published weekly snapshots."""
from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.services.projection_scoring import points_for_projection as _points_for_projection
from collegefootballfantasy_api.app.crud.projection import current_published_projections_for_weeks_query
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartWeek,PlayerChartForecast
from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_stat_weeks
from collegefootballfantasy_api.app.services.player_chart_publication import points_from_verified_stats
from collegefootballfantasy_api.app.services.player_chart_publication import verified_fantasy_week_stats
from collegefootballfantasy_api.app.services.fantasy_week_finality import week_is_authoritatively_finalized, published_finalized_weeks
from collegefootballfantasy_api.app.services.player_trade_value import PRESEASON_VALUE_POLICY_VERSION
from collegefootballfantasy_api.app.services.player_trade_value import value_snapshot_is_finalized,active_value_policy_version,current_trade_value_snapshot
from collegefootballfantasy_api.app.services.chart_forecasts import school_key, pregame_forecast, forecast_points
from datetime import datetime
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.services.league_weeks import calendar_matchup_display_week
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.schemas.player_trajectory import (
    PlayerProjectionTrajectoryPointRead,
    PlayerTrajectoryRead,
    PlayerValueTrajectoryPointRead,
)
from collegefootballfantasy_api.app.services.player_trade_value import MAX_TRADE_VALUE, VALUE_POLICY_VERSION, preseason_rating_value

WEEKS = tuple(range(1, 14))
DISPLAY_WEEKS = tuple(range(0, 14))



def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _season_projection(player: Player, *, season: int) -> float | None:
    if season==settings.current_season_year and player.sheet_projected_season_points is not None:
        return max(0.0, float(player.sheet_projected_season_points))
    return None


def _league_scoring_rules(db: Session, league_id: int | None) -> dict | None:
    if league_id is None:
        return None
    if db.get(League, league_id) is None:
        raise ValueError("league not found")
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).one_or_none()
    return settings.scoring_json if settings and settings.scoring_json else None


def _actual_points_by_week(db: Session, *, player_id: int, season: int, league_id: int | None, scoring_rules: dict | None, finalized_weeks: set[int]) -> dict[int, float]:
    player = db.get(Player, player_id)
    snapshots = db.query(PlayerChartWeek).filter_by(player_id=player_id, season=season).all()
    points = {}
    for row in snapshots:
        value = row.standard_points if league_id is None else points_from_verified_stats(row.stats_json, position=row.stats_json.get("_chart_position", player.position), rules=scoring_rules or {})
        if value is not None:
            points[row.week] = round(float(value), 1)
    # Existing finalized data can be read during rollout before staged backfill.
    # A live/stale score never becomes a historical actual on a card read.
    if league_id is not None:
        for row in db.query(PlayerWeekScore).filter_by(player_id=player_id, season=season, league_id=league_id).all():
            if row.status in {"final", "stat_corrected"} and row.week in finalized_weeks:
                points[row.week] = round(float(row.fantasy_points), 1)
    # Final box scores belong to the player's selected game, independently
    # of projected historical matchups in other leagues. Rescore the same raw
    # facts for each league; never substitute a standard total for custom rules.
    for week in WEEKS:
        if week in points:
            continue
        row = verified_fantasy_week_stats(db, season=season, week=week, players=[player], final_games_only=True).get(player_id)
        if row is None and league_id is None and week in finalized_weeks:
            row = verified_fantasy_week_stats(db, season=season, week=week, players=[player]).get(player_id)
        if row is not None:
            value = points_from_verified_stats(row.stats, position=player.position, rules=scoring_rules)
            if value is not None:
                points[week] = round(value, 1)
    return points


def build_player_trajectory(
    db: Session,
    *,
    player_id: int,
    season: int,
    league_id: int | None = None,
) -> PlayerTrajectoryRead:
    player = db.get(Player, player_id)
    if player is None:
        raise ValueError("player not found")
    league = db.get(League, league_id) if league_id is not None else None
    if league_id is not None and league is None:
        raise ValueError("league not found")
    scoring_rules = _league_scoring_rules(db, league_id)
    schedules = [row for row in db.query(TeamSchedule).filter(TeamSchedule.season == season, TeamSchedule.week.in_(range(0,14))).all() if school_key(row.team_name) == school_key(player.school)]
    schedule_by_week = {row.week: row for row in schedules}
    opening_source_week=fantasy_stat_weeks(db,season=season,week=1,player_ids={player.id})[player.id]
    if opening_source_week==0:
        schedule_by_week[1]=schedule_by_week.get(0)
    frozen_forecasts = {r.week:r.snapshot_json for r in db.query(PlayerChartForecast).filter_by(player_id=player.id,season=season).all()}
    published_by_week = {
        row.week: row for row in db.scalars(current_published_projections_for_weeks_query(
            season=season, weeks=WEEKS, player_ids=(player.id,),
        ))
    }
    certified_weeks = {week for week in WEEKS if week_is_authoritatively_finalized(db, season=season, week=week)}
    actual_by_week = _actual_points_by_week(
        db,
        player_id=player.id,
        season=season,
        league_id=league_id,
        scoring_rules=scoring_rules,
        finalized_weeks=certified_weeks,
    )
    stored_by_week = {row.week: row for row in db.query(PlayerChartWeek).filter_by(player_id=player.id,season=season).all()}
    season_projection = _season_projection(player,season=season)
    # A season total is metadata only. It is never divided, repeated, or
    # emitted as a weekly graph point; this series is canonical weekly data.
    projection: list[PlayerProjectionTrajectoryPointRead] = []
    finalized_weeks = certified_weeks | set(actual_by_week) | published_finalized_weeks(db,season=season)
    # Durable publication remains authoritative when another league is added
    # later with projected historical matchups. Do not move the forecast back
    # over already finalized player history.
    last_finalized_week = max(finalized_weeks,default=0)
    upcoming_week = last_finalized_week+1
    # Missing older publications must not hide a real current-week forecast.
    # The app calendar chooses only the forecast; it never certifies actuals.
    display_week = max(upcoming_week, calendar_matchup_display_week(season)) if season == settings.current_season_year else upcoming_week
    if display_week in published_by_week or display_week in frozen_forecasts:
        upcoming_week = display_week
    for week in WEEKS:
        if week>last_finalized_week and week != upcoming_week:
            continue
        schedule, row = schedule_by_week.get(week), published_by_week.get(week)
        finalized = week in finalized_weeks
        if not finalized and week!=upcoming_week:
            # A delayed earlier week is a gap, not a second dotted current
            # forecast or a calendar-inferred final result.
            bye=bool(schedule and (schedule.is_bye or schedule.location=="bye"))
            projection.append(PlayerProjectionTrajectoryPointRead(week=week,points=None,source="bye" if bye else "unavailable",is_finalized=False,projection_status="BYE" if bye else "AWAITING_WEEK_FINALITY"))
            continue
        original = frozen_forecasts.get(week)
        if finalized:
            stored = stored_by_week.get(week)
            original = (stored.stats_json.get("_chart_forecast") or original) if stored and "_chart_forecast" in stored.stats_json else pregame_forecast(db,player=player,season=season,week=week,schedule=schedule)
        projected_points = forecast_points(original,scoring_rules) if original else (_points_for_projection(player,row,scoring_rules) if row and not finalized else None)
        if schedule and (schedule.is_bye or schedule.location == "bye") and week not in actual_by_week:
            projection.append(PlayerProjectionTrajectoryPointRead(week=week, points=None, source="bye", projection_status="BYE", is_finalized=finalized))
        elif row is not None or original is not None or finalized:
            projection.append(PlayerProjectionTrajectoryPointRead(
                week=week,
                points=round(projected_points, 1) if projected_points is not None else None,
                actual_points=actual_by_week.get(week),
                source="unavailable" if finalized and week not in actual_by_week else ("published" if original or (row and not finalized) else "actual"),
                is_finalized=finalized,
                projection_status="MISSING_FINAL_STATS" if finalized and week not in actual_by_week else (original["projection_status"] if original else row.projection_status if row else "ACTUAL_ONLY"),
                projection_version=original["projection_version"] if original else (row.projection_version if row and not finalized else None),
                published_at=datetime.fromisoformat(original["published_at"]) if original else (row.updated_at if row and not finalized else None),
            ))

    published_values = {
        row.week: row
        for row in db.query(PlayerTradeValue)
        .filter(PlayerTradeValue.player_id == player.id, PlayerTradeValue.season == season, PlayerTradeValue.policy_version==VALUE_POLICY_VERSION, PlayerTradeValue.week.in_(WEEKS))
        .all()
    }
    preseason_value = db.query(PlayerTradeValue).filter_by(player_id=player.id, season=season, week=0, policy_version=PRESEASON_VALUE_POLICY_VERSION).one_or_none()
    authoritative_preseason_value = preseason_rating_value(player) if season==settings.current_season_year else None
    if season==settings.current_season_year and active_value_policy_version(db,season=season)==PRESEASON_VALUE_POLICY_VERSION:
        # Before Week 1 closes, share the card's existing availability-adjusted
        # policy instead of displaying a stale stored or unadjusted baseline.
        current=current_trade_value_snapshot(db,player_id=player.id,season=season)
        authoritative_preseason_value=current["value"] if current else None
        preseason_value=None
    value: list[PlayerValueTrajectoryPointRead] = []
    if preseason_value is not None or authoritative_preseason_value is not None:
        value.append(PlayerValueTrajectoryPointRead(week=0, value=round(_clamp(float(preseason_value.value) if preseason_value else authoritative_preseason_value, 0.0, MAX_TRADE_VALUE), 1), source="preseason"))
    for week in WEEKS:
        existing = published_values.get(week)
        if existing is not None and value_snapshot_is_finalized(db,existing):
            value.append(PlayerValueTrajectoryPointRead(week=week, value=round(_clamp(float(existing.value), 0.0, MAX_TRADE_VALUE), 1), source="published"))

    return PlayerTrajectoryRead(player_id=player.id, season=season, league_id=league_id, projection=projection, value=value, preseason_projection_points=round(season_projection, 1) if season_projection is not None else None)
