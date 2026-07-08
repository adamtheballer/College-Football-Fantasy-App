from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def test_waiver_processing_regressions_are_covered_by_waiver_tests():
    waiver_tests = (TEST_DIR / "test_waivers.py").read_text()

    assert "test_waiver_claim_submit_list_cancel" in waiver_tests
    assert "test_admin_processes_faab_claims_by_bid_and_records_failure" in waiver_tests
    assert "test_waiver_processing_fails_if_drop_player_changed" in waiver_tests
    assert "test_waiver_claim_rejects_unavailable_player_and_overspend" in waiver_tests
