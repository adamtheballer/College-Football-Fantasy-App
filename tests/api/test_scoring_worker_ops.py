from scripts.run_scoring_worker import schedule_for_mode


def test_scoring_worker_uses_distinct_cadence_profiles():
    live = schedule_for_mode("live")
    postgame = schedule_for_mode("postgame")
    correction = schedule_for_mode("correction")

    assert live.mode == "live"
    assert postgame.mode == "postgame"
    assert correction.mode == "correction"
    assert live.interval_seconds < postgame.interval_seconds <= correction.interval_seconds
