from collegefootballfantasy_api.app.crud.projection import get_projection, list_projections
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


def test_public_projection_reads_use_one_corrected_snapshot_per_player(db_session):
    player = Player(name="Versioned Projection", position="RB", school="Texas")
    db_session.add(player)
    db_session.flush()
    db_session.add_all(
        [
            WeeklyProjection(
                player_id=player.id,
                season=2026,
                week=1,
                projection_version="PRESEASON",
                is_published=True,
                fantasy_points=28.9,
            ),
            WeeklyProjection(
                player_id=player.id,
                season=2026,
                week=1,
                projection_version="CORRECTED_2",
                is_published=True,
                fantasy_points=20.9,
            ),
            WeeklyProjection(
                player_id=player.id,
                season=2026,
                week=1,
                projection_version="FINAL",
                is_published=False,
                fantasy_points=24.1,
            ),
        ]
    )
    db_session.commit()

    rows, total = list_projections(db_session, season=2026, week=1)
    projection = get_projection(db_session, player.id, season=2026, week=1)

    assert total == 1
    assert len(rows) == 1
    assert rows[0].projection_version == "CORRECTED_2"
    assert rows[0].fantasy_points == 20.9
    assert projection is not None
    assert projection.projection_version == "CORRECTED_2"
    assert projection.fantasy_points == 20.9


def test_locked_projection_wins_over_a_corrected_snapshot(db_session):
    player = Player(name="Locked Projection", position="WR", school="Alabama")
    db_session.add(player)
    db_session.flush()
    db_session.add_all(
        [
            WeeklyProjection(
                player_id=player.id,
                season=2026,
                week=1,
                projection_version="CORRECTED",
                is_published=True,
                fantasy_points=16.2,
            ),
            WeeklyProjection(
                player_id=player.id,
                season=2026,
                week=1,
                projection_version="LOCKED",
                is_published=True,
                fantasy_points=15.4,
            ),
        ]
    )
    db_session.commit()

    projection = get_projection(db_session, player.id, season=2026, week=1)

    assert projection is not None
    assert projection.projection_version == "LOCKED"
    assert projection.fantasy_points == 15.4
