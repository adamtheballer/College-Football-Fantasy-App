from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections
from collegefootballfantasy_api.app.services.projections.usage import compute_usage_shares


def _player(player_id: int, name: str, position: str) -> Player:
    return Player(
        id=player_id,
        name=name,
        position=position,
        school="Test University",
        cfb27_overall=90,
        cfb27_position_rank=1,
    )


def test_postgame_usage_keeps_default_targets_when_provider_omits_team_targets() -> None:
    running_back = _player(1, "Running Back", "RB")
    receiver = _player(2, "Receiver", "WR")
    players = [running_back, receiver]
    # ESPN can supply carries without a target field for a final box score.
    # That omission must not make every receiver a zero-volume projection.
    stats = {running_back.id: {"RushingAttempts": 20, "RushingYards": 100}}

    usage = {
        row.player_id: row
        for row in compute_usage_shares(players, stats, season=2026, week=2)
    }

    assert usage[receiver.id].target_share > 0
    assert usage[running_back.id].rush_share < 1
    projections = build_weekly_projections(
        players=players,
        team_env_by_team={},
        usage_by_player=usage,
        defense_by_team={},
        player_stats=stats,
        injuries_by_player={},
        opponent_by_team={},
        season=2026,
        week=2,
    )
    projected_by_player_id = {projection.player_id: projection for projection in projections}
    assert projected_by_player_id[receiver.id].fantasy_points > 0


def test_espn_snake_case_stats_match_legacy_usage_and_efficiency() -> None:
    from collegefootballfantasy_api.app.services.projections.efficiency import compute_efficiency

    players = [_player(1, "Starter", "RB"), _player(2, "Reserve", "RB")]
    legacy = {1: {"RushingAttempts": 19, "RushingYards": 62}, 2: {"RushingAttempts": 7, "RushingYards": 33}}
    espn = {1: {"rushing_attempts": 19, "rush_yards": 62}, 2: {"rushing_attempts": 7, "rush_yards": 33}}
    old_usage = compute_usage_shares(players, legacy, 2026, 12)
    new_usage = compute_usage_shares(players, espn, 2026, 12)
    assert [row.rush_share for row in new_usage] == [row.rush_share for row in old_usage]
    assert compute_efficiency(espn[1], "RB") == compute_efficiency(legacy[1], "RB")
    qb_stats = {"passing_attempts": 30, "completions": 21, "pass_yards": 240, "pass_tds": 2, "interceptions": 1}
    efficiency = compute_efficiency(qb_stats, "QB")
    assert 0.62 < efficiency["comp_pct"] < 0.7
    assert 7.5 < efficiency["ypa"] < 8
    # One long run must not project its full rate over every future carry.
    assert compute_efficiency({"rushing_attempts": 1, "rush_yards": 67}, "RB")["ypc"] < 9


def test_season_ending_absence_sets_zero_projection_and_out_status() -> None:
    from collegefootballfantasy_api.app.models.injury import Injury

    player = _player(1, "Unavailable", "RB")
    projections = build_weekly_projections(
        players=[player], team_env_by_team={}, usage_by_player={}, defense_by_team={},
        player_stats={}, injuries_by_player={player.id: Injury(status="OUT_FOR_SEASON")},
        opponent_by_team={}, season=2026, week=12,
    )
    assert projections[0].fantasy_points == 0
    assert projections[0].availability_multiplier == 0
    assert projections[0].projection_status == "OUT"
