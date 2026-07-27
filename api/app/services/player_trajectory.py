"""Build read-only, player-specific 13-week card trajectories.

Published weekly rows are always authoritative.  Before a weekly row exists,
the graph uses the same durable inputs the projection pipeline uses instead of
inventing a generic visual line: schedule, team environment, opponent defense,
usage, availability, and the player's season projection.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.player_trajectory import (
    PlayerProjectionTrajectoryPointRead,
    PlayerTrajectoryRead,
    PlayerValueTrajectoryPointRead,
)
from collegefootballfantasy_api.app.services.player_trade_value import VALUE_POLICY_VERSION

WEEKS = tuple(range(1, 14))
POSITION_SCARCITY = {"QB": 38.0, "RB": 58.0, "WR": 55.0, "TE": 62.0, "K": 25.0, "PK": 25.0}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _latest_by_week(rows: Iterable[object], *, week: int) -> object | None:
    eligible = [row for row in rows if getattr(row, "week", 0) <= week]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (getattr(row, "week", 0), getattr(row, "id", 0)))


def _published_projection_by_week(rows: Iterable[WeeklyProjection]) -> dict[int, WeeklyProjection]:
    by_week: dict[int, WeeklyProjection] = {}
    for row in rows:
        current = by_week.get(row.week)
        if current is None or (row.locked_at is not None, row.updated_at, row.id) > (current.locked_at is not None, current.updated_at, current.id):
            by_week[row.week] = row
    return by_week


def _projection_stats(row: WeeklyProjection) -> dict[str, float]:
    return {
        "pass_yards": float(row.pass_yards or 0.0),
        "pass_tds": float(row.pass_tds or 0.0),
        "interceptions": float(row.interceptions or 0.0),
        "rush_yards": float(row.rush_yards or 0.0),
        "rush_tds": float(row.rush_tds or 0.0),
        "receptions": float(row.receptions or 0.0),
        "rec_yards": float(row.rec_yards or 0.0),
        "rec_tds": float(row.rec_tds or 0.0),
        "fg_made_0_39": float(row.field_goals_made_0_to_39 or row.field_goals_made_0_to_49 or 0.0),
        "fg_made_40_49": float(row.field_goals_made_40_to_49 or 0.0),
        "fg_made_50_plus": float(row.field_goals_made_50_plus or 0.0),
        "xp_made": float(row.extra_points_made or 0.0),
    }


def _points_for_projection(player: Player, row: WeeklyProjection, scoring_rules: dict | None) -> float:
    stats = _projection_stats(row)
    if not scoring_rules or not any(stats.values()):
        return max(0.0, float(row.fantasy_points or 0.0))
    points, _ = calculate_player_fantasy_points(stats, scoring_rules, player.position)
    return max(0.0, points)


def _season_projection(db: Session, player: Player) -> float:
    if player.sheet_projected_season_points is not None:
        return max(0.0, float(player.sheet_projected_season_points))
    fallback = (
        db.query(Player.sheet_projected_season_points)
        .filter(
            Player.id != player.id,
            func.lower(Player.name) == player.name.lower(),
            func.lower(Player.school) == player.school.lower(),
            func.upper(Player.position) == player.position.upper(),
            Player.sheet_projected_season_points.isnot(None),
        )
        .order_by(Player.sheet_synced_at.desc().nullslast(), Player.updated_at.desc())
        .first()
    )
    return max(0.0, float(fallback[0])) if fallback and fallback[0] is not None else 0.0


def _availability_multiplier(status: str | None) -> float:
    return {
        "OUT": 0.0,
        "SUSPENDED": 0.0,
        "INELIGIBLE": 0.0,
        "DOUBTFUL": 0.25,
        "QUESTIONABLE": 0.72,
        "PROBABLE": 0.90,
        "LIMITED": 0.80,
    }.get((status or "ACTIVE").upper(), 1.0)


def _environment_multiplier(environment: TeamEnvironment | None) -> float:
    if environment is None or environment.expected_points <= 0:
        return 1.0
    return _clamp(float(environment.expected_points) / 27.0, 0.72, 1.35)


def _defense_multiplier(player: Player, defense: DefenseRating | None) -> float:
    if defense is None:
        return 1.0
    position = player.position.upper()
    if position in {"QB", "WR", "TE"}:
        values = [defense.pass_yards_multiplier, defense.pass_catch_multiplier, defense.pass_td_multiplier]
    elif position == "RB":
        values = [defense.rush_yards_multiplier, defense.rush_success_multiplier, defense.rush_td_multiplier]
    else:
        values = [defense.pass_td_multiplier, defense.rush_td_multiplier]
    return _clamp(sum(float(value or 1.0) for value in values) / len(values), 0.70, 1.35)


def _usage_multiplier(usage: UsageShare | None) -> float:
    if usage is None:
        return 1.0
    return _clamp(float(usage.applied_usage_multiplier or usage.raw_usage_multiplier or 1.0), 0.55, 1.55)


def _league_scoring_rules(db: Session, league_id: int | None) -> dict | None:
    if league_id is None:
        return None
    if db.get(League, league_id) is None:
        raise ValueError("league not found")
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).one_or_none()
    return settings.scoring_json if settings and settings.scoring_json else None


def _modeled_projection_points(
    player: Player,
    *,
    week: int,
    base_points: float,
    schedule: TeamSchedule | None,
    environments: list[TeamEnvironment],
    defenses: list[DefenseRating],
    usage_rows: list[UsageShare],
    injuries: list[Injury],
) -> float:
    if schedule and (schedule.is_bye or schedule.location == "bye"):
        return 0.0
    environment = _latest_by_week(environments, week=week)
    usage = _latest_by_week(usage_rows, week=week)
    injury = _latest_by_week(injuries, week=week)
    defense = None
    if schedule and schedule.opponent_name:
        matching = [row for row in defenses if row.team_name.lower() == schedule.opponent_name.lower()]
        defense = _latest_by_week(matching, week=week)
    return round(
        max(
            0.0,
            base_points
            * _environment_multiplier(environment if isinstance(environment, TeamEnvironment) else None)
            * _defense_multiplier(player, defense if isinstance(defense, DefenseRating) else None)
            * _usage_multiplier(usage if isinstance(usage, UsageShare) else None)
            * _availability_multiplier(injury.status if isinstance(injury, Injury) else None),
        ),
        1,
    )


def _estimated_value(db: Session, player: Player, season_projection: float) -> float:
    pool = db.query(Player).filter(func.upper(Player.position) == player.position.upper()).all()
    season_values = sorted(float(row.sheet_projected_season_points) for row in pool if row.sheet_projected_season_points is not None)
    rating_values = sorted(float(row.cfb27_overall) for row in pool if row.cfb27_overall is not None)

    def percentile(value: float | None, values: list[float], fallback: float) -> float:
        if value is None or not values:
            return fallback
        return 100 * sum(candidate <= value for candidate in values) / len(values)

    season_score = percentile(season_projection if season_projection > 0 else None, season_values, 35.0)
    rating_score = percentile(float(player.cfb27_overall) if player.cfb27_overall is not None else None, rating_values, season_score)
    scarcity = POSITION_SCARCITY.get(player.position.upper(), 45.0)
    # Seasonal outlook is intentionally the dominant preseason input; CFB27 is a secondary quality signal.
    return round(_clamp((0.60 * season_score) + (0.30 * rating_score) + (0.10 * scarcity), 0.0, 100.0), 1)


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
    scoring_rules = _league_scoring_rules(db, league_id)
    schedules = db.query(TeamSchedule).filter(TeamSchedule.team_name == player.school, TeamSchedule.season == season, TeamSchedule.week.in_(WEEKS)).all()
    schedule_by_week = {row.week: row for row in schedules}
    published_rows = db.query(WeeklyProjection).filter(WeeklyProjection.player_id == player.id, WeeklyProjection.season == season, WeeklyProjection.week.in_(WEEKS), WeeklyProjection.is_published.is_(True)).all()
    published_by_week = _published_projection_by_week(published_rows)
    environments = db.query(TeamEnvironment).filter(TeamEnvironment.team_name == player.school, TeamEnvironment.season == season, TeamEnvironment.week.in_(WEEKS)).all()
    defenses = db.query(DefenseRating).filter(DefenseRating.season == season, DefenseRating.week.in_(WEEKS)).all()
    usage_rows = db.query(UsageShare).filter(UsageShare.player_id == player.id, UsageShare.season == season, UsageShare.week.in_(WEEKS)).all()
    injuries = db.query(Injury).filter(Injury.player_id == player.id, Injury.season == season, Injury.week.in_(WEEKS)).all()
    scheduled_games = sum(1 for week in WEEKS if not (schedule_by_week.get(week) and (schedule_by_week[week].is_bye or schedule_by_week[week].location == "bye")))
    known_points = [_points_for_projection(player, row, scoring_rules) for row in published_by_week.values()]
    season_projection = _season_projection(db, player)
    base_points = season_projection / max(scheduled_games, 1) if season_projection > 0 else (sum(known_points) / len(known_points) if known_points else 0.0)

    projection: list[PlayerProjectionTrajectoryPointRead] = []
    for week in WEEKS:
        schedule = schedule_by_week.get(week)
        if schedule and (schedule.is_bye or schedule.location == "bye"):
            projection.append(PlayerProjectionTrajectoryPointRead(week=week, points=0.0, source="bye"))
        elif week in published_by_week:
            projection.append(PlayerProjectionTrajectoryPointRead(week=week, points=round(_points_for_projection(player, published_by_week[week], scoring_rules), 1), source="published"))
        else:
            projection.append(PlayerProjectionTrajectoryPointRead(week=week, points=_modeled_projection_points(player, week=week, base_points=base_points, schedule=schedule, environments=environments, defenses=defenses, usage_rows=usage_rows, injuries=injuries), source="modeled"))

    published_values = {
        row.week: row
        for row in db.query(PlayerTradeValue)
        .filter(PlayerTradeValue.player_id == player.id, PlayerTradeValue.season == season, PlayerTradeValue.policy_version == VALUE_POLICY_VERSION, PlayerTradeValue.week.in_(WEEKS))
        .all()
    }
    base_value = float(max(published_values.values(), key=lambda row: row.week).value) if published_values else _estimated_value(db, player, season_projection)
    average_points = sum(point.points for point in projection) / max(len([point for point in projection if point.source != "bye"]), 1)
    value: list[PlayerValueTrajectoryPointRead] = []
    for point in projection:
        existing = published_values.get(point.week)
        if existing:
            value.append(PlayerValueTrajectoryPointRead(week=point.week, value=round(_clamp(float(existing.value), 0.0, 100.0), 1), source="published"))
            continue
        relative_outlook = ((point.points / average_points) - 1.0) if average_points > 0 else 0.0
        value.append(PlayerValueTrajectoryPointRead(week=point.week, value=round(_clamp(base_value + (relative_outlook * 10.0), 0.0, 100.0), 1), source="modeled"))

    return PlayerTrajectoryRead(player_id=player.id, season=season, league_id=league_id, projection=projection, value=value)
