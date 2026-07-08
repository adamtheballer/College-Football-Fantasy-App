from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.player import (
    PlayerCardInjuryRead,
    PlayerPoolList,
    PlayerPoolRowRead,
)
from collegefootballfantasy_api.app.services.player_availability import (
    PlayerAvailabilityContext,
    build_availability_context,
    ownership_percentage,
    player_availability,
)
from collegefootballfantasy_api.app.services.player_pool_filters import generated_test_player_filter
from collegefootballfantasy_api.app.services.power4 import conference_for_school, resolve_power4_school
from collegefootballfantasy_api.app.services.projection_scoring_service import (
    calculate_league_projection_points,
    calculate_league_projection_range,
)
from collegefootballfantasy_api.app.services.projections.confidence import confidence_label, uncertainty_labels


def _positions(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def _projection_dict(projection: WeeklyProjection | None, scoring_json: dict | None = None) -> dict | None:
    if not projection:
        return None
    points = projection.fantasy_points
    floor = projection.floor
    ceiling = projection.ceiling
    breakdown = None
    context = "default"
    if scoring_json is not None:
        points, breakdown = calculate_league_projection_points(projection, scoring_json)
        floor, ceiling = calculate_league_projection_range(projection, scoring_json)
        context = "league"
    return {
        "season": projection.season,
        "week": projection.week,
        "fantasy_points": points,
        "floor": floor,
        "ceiling": ceiling,
        "boom_prob": projection.boom_prob,
        "bust_prob": projection.bust_prob,
        "breakdown": breakdown,
        "scoring_context": context,
        "projection_version": projection.projection_version,
        "model_version": projection.model_version,
        "input_snapshot_hash": projection.input_snapshot_hash,
        "generated_at": projection.generated_at.isoformat() if projection.generated_at else None,
        "source_freshness": projection.source_freshness,
        "confidence_score": projection.confidence_score,
        "confidence_label": confidence_label(projection.confidence_score),
        "uncertainty_labels": uncertainty_labels(
            confidence_score=projection.confidence_score,
            source_freshness=projection.source_freshness,
        ),
    }


def _injury_read(row: Injury | None) -> PlayerCardInjuryRead | None:
    if not row:
        return None
    return PlayerCardInjuryRead(
        id=row.id,
        season=row.season,
        week=row.week,
        status=row.status,
        normalized_status=row.normalized_status,
        injury=row.injury,
        body_part=row.body_part,
        return_timeline=row.return_timeline,
        practice_level=row.practice_level,
        is_game_time_decision=row.is_game_time_decision,
        is_returning=row.is_returning,
        notes=row.notes,
        source=row.source,
        source_updated_at=row.source_updated_at,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        cleared_at=row.cleared_at,
        updated_at=row.updated_at,
    )


def _trend_dict(db: Session, *, league_id: int | None, player_id: int, season: int, week: int | None) -> dict | None:
    if league_id is None or week is None:
        return None
    rows = (
        db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.player_id == player_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week <= week,
        )
        .order_by(PlayerWeekScore.week.desc())
        .limit(3)
        .all()
    )
    if not rows:
        return None
    points = [float(row.fantasy_points or 0.0) for row in rows]
    return {
        "last_games": len(points),
        "average_points": round(sum(points) / len(points), 2),
        "latest_points": points[0],
        "direction": "up" if len(points) >= 2 and points[0] > points[-1] else "flat",
    }


def _base_player_stmt() -> Select:
    return select(Player).where(generated_test_player_filter())


def _apply_filters(
    stmt: Select,
    *,
    search: str | None,
    position: str | None,
    team: str | None,
) -> Select:
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(or_(Player.name.ilike(pattern), Player.school.ilike(pattern), Player.position.ilike(pattern)))
    positions = _positions(position)
    if len(positions) == 1:
        stmt = stmt.where(Player.position == positions[0])
    elif positions:
        stmt = stmt.where(Player.position.in_(positions))
    if team:
        stmt = stmt.where(Player.school.ilike(f"%{team.strip()}%"))
    return stmt


def list_player_pool(
    db: Session,
    *,
    current_user,
    league: League | None,
    season: int | None,
    week: int | None,
    limit: int,
    offset: int,
    search: str | None = None,
    position: str | None = None,
    team: str | None = None,
    conference: str | None = None,
    availability: str | None = None,
    injury_status: str | None = None,
    sort: str | None = None,
) -> PlayerPoolList:
    capped_limit = max(1, min(limit, 200))
    league_id = league.id if league else None
    target_season = season or (league.season_year if league else 2026)
    target_week = week or 1
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first() if league_id else None
    scoring_json = settings.scoring_json if settings else None
    context = build_availability_context(db, league_id=league_id, current_user=current_user)

    stmt = _apply_filters(
        _base_player_stmt(),
        search=search,
        position=position,
        team=team,
    )
    if injury_status:
        injured_player_ids = select(Injury.player_id).where(
            Injury.season == target_season,
            Injury.week == target_week,
            Injury.status == injury_status.upper(),
        )
        stmt = stmt.where(Player.id.in_(injured_player_ids))

    players = list(db.scalars(stmt).all())
    filtered: list[Player] = []
    availability_by_player = {}
    for player in players:
        if conference:
            normalized_conference = conference.upper().replace(" ", "")
            canonical_school = resolve_power4_school(player.school or "") or player.school
            if conference_for_school(canonical_school) != normalized_conference:
                continue
        player_status = player_availability(db, player=player, league=league, context=context)
        availability_by_player[player.id] = player_status
        if availability and player_status.status != availability:
            continue
        filtered.append(player)

    projection_by_player = {
        row.player_id: row
        for row in db.query(WeeklyProjection)
        .filter(WeeklyProjection.season == target_season, WeeklyProjection.week == target_week)
        .all()
    }
    injury_by_player = {
        row.player_id: row
        for row in db.query(Injury)
        .filter(Injury.season == target_season, Injury.week == target_week)
        .all()
    }

    def sort_key(player: Player) -> tuple:
        projection = projection_by_player.get(player.id)
        projected_points = _projection_dict(projection, scoring_json)["fantasy_points"] if projection else 0.0
        trend = _trend_dict(db, league_id=league_id, player_id=player.id, season=target_season, week=target_week)
        if sort in {"projection", "projected_points"}:
            return (-float(projected_points or 0.0), player.name.lower(), player.id)
        if sort in {"recent_points", "trend"}:
            return (-(trend or {}).get("average_points", 0.0), player.name.lower(), player.id)
        if sort == "ownership":
            return (-ownership_percentage(db, player.id, season_year=target_season), player.name.lower(), player.id)
        if sort == "adp":
            return (player.sheet_adp is None, float(player.sheet_adp or 9_999_999), player.name.lower(), player.id)
        if sort == "team":
            return (player.school.lower(), player.name.lower(), player.id)
        if sort == "position":
            return (player.position, player.name.lower(), player.id)
        return (player.name.lower(), player.id)

    filtered.sort(key=sort_key)
    total = len(filtered)
    page = filtered[offset : offset + capped_limit]
    rows = [
        PlayerPoolRowRead(
            player=player,
            availability=availability_by_player[player.id],
            ownership_percentage=ownership_percentage(db, player.id, season_year=target_season),
            projection=_projection_dict(projection_by_player.get(player.id), scoring_json),
            injury=_injury_read(injury_by_player.get(player.id)),
            recent_trend=_trend_dict(db, league_id=league_id, player_id=player.id, season=target_season, week=target_week),
            watchlisted=player.id in context.watchlisted_player_ids,
        )
        for player in page
    ]
    return PlayerPoolList(data=rows, total=total, limit=capped_limit, offset=offset)
