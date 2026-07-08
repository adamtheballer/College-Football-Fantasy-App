from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def test_draft_race_condition_regressions_are_covered_by_draft_room_tests():
    draft_tests = (TEST_DIR / "test_draft_room.py").read_text()

    assert "test_two_user_real_draft_stays_in_sync_and_creates_rosters" in draft_tests
    assert "test_duplicate_draft_pick_returns_409_and_does_not_create_extra_rows" in draft_tests
    assert "test_draft_pick_integrity_error_returns_409_and_rolls_back" in draft_tests
    assert "with_for_update" in (Path(__file__).resolve().parents[2] / "api" / "app" / "services" / "draft_service.py").read_text()
