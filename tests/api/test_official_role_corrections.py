from collegefootballfantasy_api.app.crud.projection import get_projection
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.official_role_corrections import (
    ROLE_CORRECTION_VERSION,
    apply_tennessee_qb_starter_correction,
)
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections


def _qb(player_id: int, name: str, depth_order: int | None) -> Player:
    return Player(
        id=player_id,
        name=name,
        position="QB",
        school="Tennessee",
        depth_chart_position=f"QB{depth_order}" if depth_order else None,
        depth_order=depth_order,
        cfb27_overall=80,
        cfb27_position_rank=10,
    )


def test_projection_engine_reduces_healthy_backup_quarterback_volume():
    starter = _qb(1, "Starter", 1)
    backup = _qb(2, "Backup", 2)

    rows = build_weekly_projections(
        players=[starter, backup],
        team_env_by_team={},
        usage_by_player={},
        defense_by_team={},
        player_stats={},
        injuries_by_player={},
        opponent_by_team={},
        season=2026,
        week=1,
    )
    projections = {row.player_id: row for row in rows}

    assert projections[starter.id].pass_attempts > 30
    assert projections[backup.id].pass_attempts == projections[starter.id].pass_attempts * 0.18
    assert projections[starter.id].fantasy_points > projections[backup.id].fantasy_points * 3.5


def test_tennessee_official_role_correction_supersedes_preseason_rows(db_session):
    george = Player(
        name="George MacIntyre", position="QB", school="Tennessee",
        depth_chart_position="QB1", depth_order=1, cfb27_overall=80, cfb27_position_rank=10,
    )
    faizon = Player(
        name="Faizon Brandon", position="QB", school="Tennessee",
        depth_chart_position="QB2", depth_order=2, cfb27_overall=77, cfb27_position_rank=20,
    )
    db_session.add_all([george, faizon])
    db_session.flush()
    for player in (george, faizon):
        for week in (1, 2):
            db_session.add(
                WeeklyProjection(
                    player_id=player.id,
                    season=2026,
                    week=week,
                    projection_version="PRESEASON",
                    is_published=True,
                    fantasy_points=20.0,
                    baseline_source="sealed:preseason",
                )
            )
    db_session.commit()

    result = apply_tennessee_qb_starter_correction(
        db_session,
        season=2026,
        weeks=(1, 2),
        source_url="https://utsports.example/official-announcement",
    )
    db_session.commit()

    assert result["starter"] == "Faizon Brandon"
    assert faizon.depth_order == 1
    assert george.depth_order == 2
    role_rows = db_session.query(PlayerRoleSnapshot).filter(PlayerRoleSnapshot.season == 2026).all()
    assert {(row.player_id, row.week, row.depth_order, row.role_status) for row in role_rows} == {
        (faizon.id, 1, 1, "starter"),
        (faizon.id, 2, 1, "starter"),
        (george.id, 1, 2, "backup"),
        (george.id, 2, 2, "backup"),
    }
    faizon_week_one = get_projection(db_session, faizon.id, season=2026, week=1)
    george_week_one = get_projection(db_session, george.id, season=2026, week=1)
    assert faizon_week_one is not None and george_week_one is not None
    assert faizon_week_one.projection_version == ROLE_CORRECTION_VERSION
    assert george_week_one.projection_version == ROLE_CORRECTION_VERSION
    assert faizon_week_one.fantasy_points > george_week_one.fantasy_points
