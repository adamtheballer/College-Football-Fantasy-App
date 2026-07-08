from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def test_stat_correction_regressions_are_covered_by_finalization_tests():
    stat_tests = (TEST_DIR / "test_stat_finalization_corrections.py").read_text()

    assert "test_live_recalculation_does_not_update_standings_until_final" in stat_tests
    assert "test_finalize_league_week_scores_marks_matchups_final_and_updates_standings" in stat_tests
    assert "test_stat_correction_recalculates_scores_standings_and_records_audit" in stat_tests
    assert "test_stat_correction_recalculates_all_leagues_using_global_stat_row" in stat_tests
