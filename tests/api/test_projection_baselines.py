from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.services.projections.engine import build_weekly_projections


def _player(player_id: int, position: str, *, overall: int, position_rank: int = 1) -> Player:
    return Player(
        id=player_id,
        name=f"{position} Player {player_id}",
        position=position,
        school=f"School {player_id}",
        cfb27_overall=overall,
        cfb27_position_rank=position_rank,
    )


def test_preseason_baselines_cover_supported_draft_positions_without_provider_data() -> None:
    players = [
        _player(1, "QB", overall=96),
        _player(2, "RB", overall=96),
        _player(3, "WR", overall=96),
        _player(4, "TE", overall=90),
        _player(5, "K", overall=88),
    ]

    projections = build_weekly_projections(
        players=players,
        team_env_by_team={},
        usage_by_player={},
        defense_by_team={},
        player_stats={},
        injuries_by_player={},
        opponent_by_team={},
        season=2026,
        week=1,
    )

    assert {projection.player_id for projection in projections} == {1, 2, 3, 4, 5}
    assert all(projection.fantasy_points > 0 for projection in projections)
    assert all(projection.ceiling > projection.fantasy_points >= projection.floor for projection in projections)


def test_preseason_baselines_prefer_higher_ranked_players_at_the_same_position() -> None:
    starter = _player(1, "RB", overall=96, position_rank=1)
    reserve = _player(2, "RB", overall=82, position_rank=10)

    projections = build_weekly_projections(
        players=[starter, reserve],
        team_env_by_team={},
        usage_by_player={},
        defense_by_team={},
        player_stats={},
        injuries_by_player={},
        opponent_by_team={},
        season=2026,
        week=1,
    )
    by_player_id = {projection.player_id: projection for projection in projections}

    assert by_player_id[starter.id].fantasy_points > by_player_id[reserve.id].fantasy_points


def test_preseason_baselines_replace_zero_volume_team_environment_rows() -> None:
    player = _player(1, "WR", overall=99)
    zero_volume_environment = TeamEnvironment(
        team_name=player.school,
        season=2026,
        week=1,
        expected_plays=0.0,
        pass_rate=0.0,
        rush_rate=0.0,
    )

    projections = build_weekly_projections(
        players=[player],
        team_env_by_team={player.school: zero_volume_environment},
        usage_by_player={},
        defense_by_team={},
        player_stats={},
        injuries_by_player={},
        opponent_by_team={},
        season=2026,
        week=1,
    )

    assert projections[0].fantasy_points > 10.0
