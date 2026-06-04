from api.app.models.team import Team
from api.app.services import draft_service


def test_draft_service_snake_pick_helper_handles_forward_and_reverse_rounds():
    teams = [
        Team(id=10, league_id=1, name="Team 1", owner_user_id=1),
        Team(id=20, league_id=1, name="Team 2", owner_user_id=2),
        Team(id=30, league_id=1, name="Team 3", owner_user_id=3),
    ]

    assert draft_service.get_draft_pick_team_for_number(teams, 1) == (1, 1, teams[0])
    assert draft_service.get_draft_pick_team_for_number(teams, 3) == (1, 3, teams[2])
    assert draft_service.get_draft_pick_team_for_number(teams, 4) == (2, 1, teams[2])
    assert draft_service.get_draft_pick_team_for_number(teams, 6) == (2, 3, teams[0])


def test_draft_service_snake_pick_helper_handles_empty_order():
    assert draft_service.get_draft_pick_team_for_number([], 1) == (0, 0, None)
    assert draft_service.get_draft_pick_team_for_number([], 0) == (0, 0, None)
