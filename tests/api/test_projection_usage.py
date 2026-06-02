from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.projections.usage import compute_usage_shares


def _player(player_id: int, name: str, position: str, school: str = "Ohio State") -> Player:
    return Player(id=player_id, name=name, position=position, school=school)


def test_usage_infers_targets_from_receptions_when_targets_missing() -> None:
    players = [
        _player(1, "Jeremiah Smith", "WR"),
        _player(2, "Brandon Inniss", "WR"),
        _player(3, "Nate Roberts", "TE"),
        _player(4, "Bo Jackson", "RB"),
        _player(5, "Julian Sayin", "QB"),
    ]
    player_stats = {
        1: {"Receptions": 87, "ReceivingYards": 1243},
        2: {"Receptions": 29, "ReceivingYards": 220},
        3: {"Receptions": 22, "ReceivingYards": 240},
        4: {"RushingAttempts": 170, "Receptions": 19, "ReceivingYards": 200},
        5: {"PassingAttempts": 430, "PassingYards": 3610, "PassingTouchdowns": 32},
    }

    rows = compute_usage_shares(players, player_stats, season=2026, week=1)
    by_player = {row.player_id: row for row in rows}

    assert by_player[1].target_share > by_player[2].target_share
    assert by_player[1].target_share > 0.20
    assert by_player[5].snap_share > 0.80


def test_usage_fallback_assigns_nonzero_skill_target_shares_without_target_data() -> None:
    players = [
        _player(11, "WR One", "WR", school="Team X"),
        _player(12, "WR Two", "WR", school="Team X"),
        _player(13, "RB One", "RB", school="Team X"),
        _player(14, "TE One", "TE", school="Team X"),
        _player(15, "QB One", "QB", school="Team X"),
    ]
    player_stats = {
        11: {"ReceivingYards": 700, "Receptions": 55},
        12: {"ReceivingYards": 350, "Receptions": 30},
        13: {"RushingAttempts": 140},
        14: {"ReceivingYards": 180, "Receptions": 18},
        15: {"PassingAttempts": 360},
    }

    rows = compute_usage_shares(players, player_stats, season=2026, week=1)
    skill_target_total = sum(
        row.target_share for row in rows if row.player_id in {11, 12, 13, 14}
    )

    assert skill_target_total > 0.9
    assert skill_target_total < 1.1
