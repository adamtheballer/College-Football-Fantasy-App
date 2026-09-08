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
