from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent


def test_trade_workflow_regressions_are_covered_by_trade_tests():
    trade_tests = (TEST_DIR / "test_trades.py").read_text()

    assert "test_trade_analyze_requires_auth" in trade_tests
    assert "test_trade_offer_accept_approve_processes_atomic_roster_swap" in trade_tests
    assert "test_trade_accept_rejects_if_roster_changed" in trade_tests
    assert "test_trade_cancel_reject_and_expiry_paths" in trade_tests
