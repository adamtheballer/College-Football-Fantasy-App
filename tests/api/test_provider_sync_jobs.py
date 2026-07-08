from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def test_provider_sync_job_regressions_are_covered_by_provider_tests():
    provider_tests = (TEST_DIR / "test_provider_identity_audit.py").read_text()

    assert "test_sportsdata_provider_adapter_records_unmatched_rows" in provider_tests
    assert "test_admin_provider_sync_status_shows_freshness_and_job_history" in provider_tests
    assert "ProviderSyncJob" in provider_tests
    assert "rows_seen" in provider_tests
    assert "rows_rejected" in provider_tests
