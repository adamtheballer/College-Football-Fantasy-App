from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_season_rank import PlayerSeasonRank
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.player_season_rank_service import (
    build_verified_season_rank_snapshots,
    persist_verified_season_rank_snapshots,
)


def test_verified_positional_rank_preview_uses_only_finalized_rows_and_never_writes(db_session):
    leader = Player(name="Rank Leader", position="RB", school="Alpha")
    runner_up = Player(name="Rank Runner Up", position="RB", school="Beta")
    unverified = Player(name="Unverified Back", position="RB", school="Gamma")
    db_session.add_all((leader, runner_up, unverified))
    db_session.flush()
    db_session.add_all((
        PlayerStat(player_id=leader.id, season=2026, week=1, source="verified", verified=True, stats={"rush_yards": 120, "rush_tds": 1}),
        PlayerStat(player_id=runner_up.id, season=2026, week=1, source="verified", verified=True, stats={"rush_yards": 80, "rush_tds": 1}),
        PlayerStat(player_id=unverified.id, season=2026, week=1, source="shadow", verified=False, stats={"rush_yards": 300, "rush_tds": 4}),
    ))
    db_session.flush()

    snapshots = build_verified_season_rank_snapshots(db_session, season=2026, through_week=1)

    assert [(row.player_id, row.position, row.position_rank) for row in snapshots] == [
        (leader.id, "RB", 1),
        (runner_up.id, "RB", 2),
    ]
    assert db_session.query(PlayerSeasonRank).count() == 0


def test_certified_snapshot_persistence_is_idempotent_and_never_includes_unverified_rows(db_session):
    leader = Player(name="Certified Leader", position="WR", school="Alpha")
    runner_up = Player(name="Certified Runner Up", position="WR", school="Beta")
    shadow_only = Player(name="Shadow Only", position="WR", school="Gamma")
    db_session.add_all((leader, runner_up, shadow_only))
    db_session.flush()
    db_session.add_all((
        PlayerStat(player_id=leader.id, season=2026, week=1, source="verified", verified=True, stats={"receiving_yards": 100, "receiving_tds": 1}),
        PlayerStat(player_id=runner_up.id, season=2026, week=1, source="verified", verified=True, stats={"receiving_yards": 80, "receiving_tds": 1}),
        PlayerStat(player_id=shadow_only.id, season=2026, week=1, source="shadow", verified=False, stats={"receiving_yards": 250, "receiving_tds": 3}),
    ))
    db_session.flush()

    first = persist_verified_season_rank_snapshots(db_session, season=2026, through_week=1)
    second = persist_verified_season_rank_snapshots(db_session, season=2026, through_week=1)

    assert [(row.player_id, row.position_rank) for row in first] == [
        (leader.id, 1),
        (runner_up.id, 2),
    ]
    assert [(row.player_id, row.position_rank) for row in second] == [
        (leader.id, 1),
        (runner_up.id, 2),
    ]
    assert db_session.query(PlayerSeasonRank).filter_by(season=2026, through_week=1).count() == 2
