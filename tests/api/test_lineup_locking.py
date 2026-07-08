from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def test_lineup_locking_regressions_are_covered_by_route_and_scoring_tests():
    roster_tests = (TEST_DIR / "test_roster_workflows.py").read_text()
    scoring_tests = (TEST_DIR / "test_stat_finalization_corrections.py").read_text()

    assert "test_roster_mutations_block_locked_players_after_kickoff" in roster_tests
    assert "test_roster_mutations_allow_players_before_kickoff" in roster_tests
    assert "test_lineup_snapshot_updates_before_player_game_locks" in scoring_tests
    assert "test_lineup_snapshot_freezes_after_player_game_locks" in scoring_tests
