"""Auditable official depth-role corrections for already-published forecasts.

The sealed preseason sheets remain immutable review artifacts.  When an
official team announcement supersedes a preseason role, this module records a
week-bounded role snapshot and publishes a higher-priority replacement
projection.  The underlying sheet-backed projection is retained for audit.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections


OFFICIAL_ROLE_SOURCE = "official_team_announcement"
ROLE_CORRECTION_VERSION = "CORRECTED_ROLE"
ROLE_CORRECTION_MODEL_VERSION = "official_role_override_v1"

_COPY_COLUMNS = tuple(
    column.name
    for column in WeeklyProjection.__table__.columns
    if column.name not in {"id", "created_at", "updated_at", "player_id", "season", "week", "projection_version"}
)


def _player(db: Session, *, name: str, school: str) -> Player:
    player = db.scalar(select(Player).where(Player.name == name, Player.school == school, Player.position == "QB"))
    if player is None:
        raise ValueError(f"No exact quarterback match for {name} ({school}).")
    return player


def _upsert_role_snapshot(
    db: Session,
    *,
    player: Player,
    season: int,
    week: int,
    depth_order: int,
    role_status: str,
) -> None:
    snapshot = db.scalar(
        select(PlayerRoleSnapshot).where(
            PlayerRoleSnapshot.player_id == player.id,
            PlayerRoleSnapshot.season == season,
            PlayerRoleSnapshot.week == week,
        )
    )
    if snapshot is None:
        snapshot = PlayerRoleSnapshot(
            player_id=player.id,
            season=season,
            week=week,
            school=player.school,
            position="QB",
        )
        db.add(snapshot)
    snapshot.source = OFFICIAL_ROLE_SOURCE
    snapshot.depth_order = depth_order
    snapshot.role_status = role_status
    snapshot.school = player.school
    snapshot.position = "QB"


def _project_week(
    db: Session,
    *,
    players: list[Player],
    season: int,
    week: int,
    source_url: str,
) -> int:
    source_by_player = {
        player.id: db.scalar(
            current_published_projections_query(season=season, week=week, player_ids=(player.id,))
        )
        for player in players
    }
    missing = [player.name for player in players if source_by_player[player.id] is None]
    if missing:
        raise ValueError(f"Cannot role-correct Week {week}; no published baseline for {', '.join(missing)}.")
    locked = [player.name for player in players if source_by_player[player.id].locked_at is not None]
    if locked:
        raise ValueError(f"Cannot change locked Week {week} projections for {', '.join(locked)}.")

    schedules = db.scalars(
        select(TeamSchedule).where(TeamSchedule.season == season, TeamSchedule.week == week)
    ).all()
    opponent_by_team = {
        row.team_name: row.opponent_name
        for row in schedules
        if not row.is_bye and row.opponent_name
    }
    team_env_by_team = {
        row.team_name: row
        for row in db.scalars(
            select(TeamEnvironment).where(TeamEnvironment.season == season, TeamEnvironment.week == week)
        ).all()
    }
    defense_by_team = {
        row.team_name: row
        for row in db.scalars(
            select(DefenseRating).where(DefenseRating.season == season, DefenseRating.week == week)
        ).all()
    }
    usage_by_player = {
        row.player_id: row
        for row in db.scalars(
            select(UsageShare).where(UsageShare.season == season, UsageShare.week == week, UsageShare.player_id.in_([player.id for player in players]))
        ).all()
    }
    injuries_by_player = {
        row.player_id: row
        for row in db.scalars(
            select(Injury).where(Injury.season == season, Injury.week == week, Injury.player_id.in_([player.id for player in players]))
        ).all()
    }
    projections = build_weekly_projections(
        players=players,
        team_env_by_team=team_env_by_team,
        usage_by_player=usage_by_player,
        defense_by_team=defense_by_team,
        player_stats={},
        injuries_by_player=injuries_by_player,
        opponent_by_team=opponent_by_team,
        season=season,
        week=week,
    )
    generated_by_player = {row.player_id: row for row in projections}

    for player in players:
        candidate = generated_by_player[player.id]
        source = source_by_player[player.id]
        corrected = db.scalar(
            select(WeeklyProjection).where(
                WeeklyProjection.player_id == player.id,
                WeeklyProjection.season == season,
                WeeklyProjection.week == week,
                WeeklyProjection.projection_version == ROLE_CORRECTION_VERSION,
            )
        )
        if corrected is None:
            corrected = WeeklyProjection(
                player_id=player.id,
                season=season,
                week=week,
                projection_version=ROLE_CORRECTION_VERSION,
            )
            db.add(corrected)
        for column in _COPY_COLUMNS:
            setattr(corrected, column, getattr(candidate, column))
        # Preserve the canonical matchup linkage from the reviewed baseline.
        corrected.team_id = source.team_id
        corrected.opponent_team_id = source.opponent_team_id
        corrected.is_published = True
        corrected.locked_at = None
        corrected.projection_status = "ACTIVE"
        corrected.baseline_source = "official_team_role"
        corrected.fallback_reason = f"Official starter role: {source_url}"[:500]
        corrected.model_version = ROLE_CORRECTION_MODEL_VERSION
        corrected.confidence = 0.95

    return len(projections)


def apply_tennessee_qb_starter_correction(
    db: Session,
    *,
    season: int,
    weeks: Iterable[int],
    source_url: str,
) -> dict[str, object]:
    """Install Tennessee's officially announced Brandon/MacIntyre QB order.

    Faizon Brandon was named starter on 2026-08-25.  The correction is
    intentionally explicit rather than mutating the sealed preseason workbook.
    A subsequent official depth-chart change can supersede these snapshots.
    """

    faizon = _player(db, name="Faizon Brandon", school="Tennessee")
    george = _player(db, name="George MacIntyre", school="Tennessee")
    faizon.depth_chart_position, faizon.depth_order = "QB1", 1
    george.depth_chart_position, george.depth_order = "QB2", 2

    corrected_weeks: list[int] = []
    for week in sorted({int(value) for value in weeks}):
        if week < 1 or week > 13:
            raise ValueError("Role corrections must target regular-season weeks 1 through 13.")
        _upsert_role_snapshot(
            db, player=faizon, season=season, week=week, depth_order=1, role_status="starter"
        )
        _upsert_role_snapshot(
            db, player=george, season=season, week=week, depth_order=2, role_status="backup"
        )
        _project_week(db, players=[faizon, george], season=season, week=week, source_url=source_url)
        corrected_weeks.append(week)

    return {
        "season": season,
        "weeks": corrected_weeks,
        "starter": faizon.name,
        "backup": george.name,
        "source": source_url,
        "projection_version": ROLE_CORRECTION_VERSION,
    }
