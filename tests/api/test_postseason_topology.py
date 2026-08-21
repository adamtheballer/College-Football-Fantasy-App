import pytest

from collegefootballfantasy_api.app.services.postseason_topology import build_bracket_topology, required_rounds


@pytest.mark.parametrize("teams,expected_rounds,expected_nodes", [(2, 1, 1), (4, 2, 4), (6, 3, 7), (8, 3, 12)])
def test_fixed_bracket_topologies_have_complete_unique_nodes(teams, expected_rounds, expected_nodes):
    nodes = build_bracket_topology(teams)
    assert required_rounds(teams) == expected_rounds
    assert len(nodes) == expected_nodes
    assert len({node.key for node in nodes}) == expected_nodes
    assert max(node.round_number for node in nodes) == expected_rounds
    assert next(node for node in nodes if node.key == "championship").matchup_type == "CHAMPIONSHIP"


def test_six_team_topology_uses_real_byes_and_correct_semifinal_routes():
    nodes = {node.key: node for node in build_bracket_topology(6)}
    assert {nodes["qf_a"].team_a.value, nodes["qf_a"].team_b.value} == {3, 6}
    assert {nodes["qf_b"].team_a.value, nodes["qf_b"].team_b.value} == {4, 5}
    assert nodes["semi_a"].team_a.value == 1
    assert nodes["semi_a"].team_b.kind == "winner" and nodes["semi_a"].team_b.value == "qf_b"
    assert nodes["semi_b"].team_a.value == 2
    assert nodes["fifth_place"].team_a.kind == "loser"
    assert nodes["fifth_place"].team_b.kind == "loser"


def test_eight_team_topology_routes_losers_to_placement_path():
    nodes = {node.key: node for node in build_bracket_topology(8)}
    assert nodes["placement_semi_a"].matchup_type == "PLACEMENT_SEMIFINAL"
    assert nodes["placement_semi_a"].team_a.kind == "loser"
    assert nodes["seventh_place"].team_a.kind == "loser"
    assert nodes["seventh_place"].team_b.kind == "loser"


@pytest.mark.parametrize("value", [0, 1, 3, 5, 7, 9, 10])
def test_unsupported_bracket_sizes_fail_closed(value):
    with pytest.raises(ValueError, match="2, 4, 6, or 8"):
        build_bracket_topology(value)
