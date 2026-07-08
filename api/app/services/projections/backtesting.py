from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.projection import ProjectionBacktestRow, ProjectionBacktestSummary
from collegefootballfantasy_api.app.services.power4 import conference_for_school, resolve_power4_school


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def _bucket_for_confidence(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def build_projection_backtest(
    db: Session,
    *,
    season: int,
    week: int,
    league_id: int | None = None,
    limit: int = 100,
) -> ProjectionBacktestSummary:
    query = (
        db.query(WeeklyProjection, PlayerWeekScore, Player)
        .join(PlayerWeekScore, PlayerWeekScore.player_id == WeeklyProjection.player_id)
        .join(Player, Player.id == WeeklyProjection.player_id)
        .filter(
            WeeklyProjection.season == season,
            WeeklyProjection.week == week,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
        )
    )
    if league_id is not None:
        query = query.filter(PlayerWeekScore.league_id == league_id)

    raw_rows = query.order_by(WeeklyProjection.fantasy_points.desc(), Player.name.asc()).limit(max(1, min(limit, 500))).all()
    rows: list[ProjectionBacktestRow] = []
    errors_by_position: dict[str, list[float]] = defaultdict(list)
    bias_by_team_values: dict[str, list[float]] = defaultdict(list)
    bias_by_conference_values: dict[str, list[float]] = defaultdict(list)
    calibration: dict[str, list[float]] = defaultdict(list)

    for projection, actual, player in raw_rows:
        projected_points = float(projection.fantasy_points or 0.0)
        actual_points = float(actual.fantasy_points or 0.0)
        error = actual_points - projected_points
        absolute_error = abs(error)
        position = player.position.upper()
        team = player.school
        conference = conference_for_school(resolve_power4_school(team) or team) or "UNKNOWN"
        confidence = float(projection.confidence_score or 0.5)
        rows.append(
            ProjectionBacktestRow(
                player_id=player.id,
                player_name=player.name,
                position=position,
                team=team,
                projected_points=round(projected_points, 3),
                actual_points=round(actual_points, 3),
                error=round(error, 3),
                absolute_error=round(absolute_error, 3),
                confidence_score=round(confidence, 3),
            )
        )
        errors_by_position[position].append(absolute_error)
        bias_by_team_values[team].append(error)
        bias_by_conference_values[conference].append(error)
        calibration[_bucket_for_confidence(confidence)].append(absolute_error)

    all_errors = [row.absolute_error for row in rows]
    all_bias = [row.error for row in rows]
    return ProjectionBacktestSummary(
        season=season,
        week=week,
        league_id=league_id,
        sample_size=len(rows),
        mae=_avg(all_errors),
        bias=_avg(all_bias),
        mae_by_position={key: _avg(values) for key, values in sorted(errors_by_position.items())},
        bias_by_team={key: _avg(values) for key, values in sorted(bias_by_team_values.items())},
        bias_by_conference={key: _avg(values) for key, values in sorted(bias_by_conference_values.items())},
        confidence_calibration={
            key: {"sample_size": len(values), "mae": _avg(values)}
            for key, values in sorted(calibration.items())
        },
        rows=rows,
    )
