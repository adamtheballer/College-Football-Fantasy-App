"""Build player-card trajectories from canonical published weekly snapshots."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from collegefootballfantasy_api.app.domain.stat_normalization import normalize_player_stats
from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.player_trajectory import (
    PlayerProjectionTrajectoryPointRead,
    PlayerTrajectoryRead,
    PlayerValueTrajectoryPointRead,
)
from collegefootballfantasy_api.app.services.player_trade_value import MAX_TRADE_VALUE, VALUE_POLICY_VERSION, preseason_rating_value

WEEKS = tuple(range(1, 14))
DISPLAY_WEEKS = tuple(range(0, 14))
POSITION_SCARCITY = {"QB": 38.0, "RB": 58.0, "WR": 55.0, "TE": 62.0, "K": 25.0, "PK": 25.0}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _projection_stats(row: WeeklyProjection) -> dict[str, float]:
    # Published projection sources provide 0--39, 40--49, and 50+ volume,
    # rather than exact made-kick distances.  Split that expected volume into
    # the fixed league scoring tiers so a league's field-goal settings still
    # apply to projections; live ESPN box scores use exact distances.
    short_field_goals = float(row.field_goals_made_0_to_39 or row.field_goals_made_0_to_49 or 0.0)
    medium_field_goals = float(row.field_goals_made_40_to_49 or 0.0)
    long_field_goals = float(row.field_goals_made_50_plus or 0.0)
    return {
        "pass_yards": float(row.pass_yards or 0.0),
        "pass_tds": float(row.pass_tds or 0.0),
        "interceptions": float(row.interceptions or 0.0),
        "rush_yards": float(row.rush_yards or 0.0),
        "rush_tds": float(row.rush_tds or 0.0),
        "receptions": float(row.receptions or 0.0),
        "rec_yards": float(row.rec_yards or 0.0),
        "rec_tds": float(row.rec_tds or 0.0),
        "fg_made_0_30": short_field_goals * 0.75,
        "fg_made_31_40": short_field_goals * 0.25,
        "fg_made_41_50": medium_field_goals,
        "fg_made_51_60": long_field_goals,
        "fg_made_61_plus": 0.0,
        "xp_made": float(row.extra_points_made or 0.0),
    }


def _points_for_projection(player: Player, row: WeeklyProjection, scoring_rules: dict | None) -> float:
    # A published weekly snapshot's fantasy-points field is already its
    # authoritative scoring result. Recalculate only older rows that lack it.
    if row.fantasy_points is not None:
        return max(0.0, float(row.fantasy_points))
    stats = _projection_stats(row)
    if not scoring_rules or not any(stats.values()):
        return max(0.0, float(row.fantasy_points or 0.0))
    points, _ = calculate_player_fantasy_points(stats, scoring_rules, player.position)
    return max(0.0, points)


def _points_for_final_stat(
    player: Player,
    stat: PlayerGameStat | PlayerStat,
    scoring_rules: dict | None,
) -> float:
    for key in ("fantasy_points", "fantasyPoints", "fpts", "FantasyPoints"):
        value = (stat.stats or {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(0.0, float(value))
    points, _ = calculate_player_fantasy_points(
        normalize_player_stats(stat.stats or {}, player.position),
        scoring_rules,
        player.position,
    )
    return max(0.0, points)


def _game_is_final(game: Game | None) -> bool:
    return game is not None and game.home_points is not None and game.away_points is not None


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


def _league_scoring_rules(db: Session, league_id: int | None) -> dict | None:
    if league_id is None:
        return None
    if db.get(League, league_id) is None:
        raise ValueError("league not found")
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).one_or_none()
    return settings.scoring_json if settings and settings.scoring_json else None


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
    league = db.get(League, league_id) if league_id is not None else None
    if league_id is not None and league is None:
        raise ValueError("league not found")
    scoring_rules = _league_scoring_rules(db, league_id)
    schedules = db.query(TeamSchedule).filter(TeamSchedule.team_name == player.school, TeamSchedule.season == season, TeamSchedule.week.in_(WEEKS)).all()
    schedule_by_week = {row.week: row for row in schedules}
    game_ids = [schedule.game_id for schedule in schedules if schedule.game_id is not None]
    games_by_id = {
        game.id: game
        for game in db.query(Game).filter(Game.id.in_(game_ids or [-1])).all()
    }
    player_stats_by_week = {
        stat.week: stat
        for stat in db.query(PlayerStat)
        .filter(
            PlayerStat.player_id == player.id,
            PlayerStat.season == season,
            PlayerStat.week.in_(WEEKS),
            PlayerStat.verified.is_(True),
        )
        .all()
    }
    player_game_stats_by_game = {
        stat.game_id: stat
        for stat in db.query(PlayerGameStat)
        .filter(
            PlayerGameStat.player_id == player.id,
            PlayerGameStat.season == season,
            PlayerGameStat.game_id.in_(game_ids or [-1]),
        )
        .all()
    }
    published_by_week = {
        week: db.scalar(
            current_published_projections_query(
                season=season,
                week=week,
                player_ids=(player.id,),
            )
        )
        for week in WEEKS
    }
    published_by_week = {week: row for week, row in published_by_week.items() if row is not None}
    season_projection = _season_projection(db, player)
    # A season total is metadata only. It is never divided, repeated, or
    # emitted as a weekly graph point; this series is canonical weekly data.
    projection: list[PlayerProjectionTrajectoryPointRead] = []
    for week in WEEKS:
        schedule = schedule_by_week.get(week)
        if schedule and (schedule.is_bye or schedule.location == "bye"):
            projection.append(PlayerProjectionTrajectoryPointRead(week=week, points=None, source="bye", projection_status="BYE"))
        elif week in published_by_week:
            row = published_by_week[week]
            game = games_by_id.get(schedule.game_id) if schedule and schedule.game_id is not None else None
            actual_stat = (
                player_game_stats_by_game.get(schedule.game_id)
                if schedule and schedule.game_id is not None
                else None
            ) or player_stats_by_week.get(week)
            actual_points = (
                round(_points_for_final_stat(player, actual_stat, scoring_rules), 1)
                if actual_stat is not None and _game_is_final(game)
                else None
            )
            projection.append(
                PlayerProjectionTrajectoryPointRead(
                    week=week,
                    points=round(_points_for_projection(player, row, scoring_rules), 1),
                    actual_points=actual_points,
                    source="preweek",
                    projection_status=row.projection_status,
                    projection_version=row.projection_version,
                    published_at=row.updated_at,
                )
            )

    published_values = {
        row.week: row
        for row in db.query(PlayerTradeValue)
        .filter(PlayerTradeValue.player_id == player.id, PlayerTradeValue.season == season, PlayerTradeValue.policy_version == VALUE_POLICY_VERSION, PlayerTradeValue.week.in_(DISPLAY_WEEKS))
        .all()
    }
    preseason_value = published_values.get(0)
    authoritative_preseason_value = preseason_rating_value(player)
    value: list[PlayerValueTrajectoryPointRead] = [
        PlayerValueTrajectoryPointRead(
            week=0,
            value=round(_clamp(authoritative_preseason_value if authoritative_preseason_value is not None else (float(preseason_value.value) if preseason_value else _estimated_value(db, player, season_projection)), 0.0, MAX_TRADE_VALUE), 1),
            source="preseason",
        )
    ]
    for week in WEEKS:
        existing = published_values.get(week)
        if existing is not None:
            value.append(PlayerValueTrajectoryPointRead(week=week, value=round(_clamp(float(existing.value), 0.0, MAX_TRADE_VALUE), 1), source="published"))

    return PlayerTrajectoryRead(player_id=player.id, season=season, league_id=league_id, projection=projection, value=value, preseason_projection_points=round(season_projection, 1) if season_projection > 0 else None)
