from api.app.services.draft_engine import (
    get_round_number,
    get_round_pick,
    get_snake_team_for_pick,
    get_total_picks,
    is_draft_complete,
)


def test_total_picks_for_12_team_13_round_draft():
    roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5}

    assert get_total_picks(12, roster_slots) == 156


def test_round_9_pick_10_maps_to_overall_pick_106():
    overall_pick = 8 * 12 + 10

    assert overall_pick == 106
    assert get_round_number(overall_pick, 12) == 9
    assert get_round_pick(overall_pick, 12) == 10


def test_snake_order_reverses_on_even_rounds():
    teams = ["one", "two", "three", "four"]

    assert get_snake_team_for_pick(teams, 1) == "one"
    assert get_snake_team_for_pick(teams, 4) == "four"
    assert get_snake_team_for_pick(teams, 5) == "four"
    assert get_snake_team_for_pick(teams, 8) == "one"


def test_final_pick_completes_draft():
    assert is_draft_complete(155, 156) is False
    assert is_draft_complete(156, 156) is True
