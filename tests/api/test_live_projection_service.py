import pytest

from collegefootballfantasy_api.app.services.live_projection_service import (
    game_progress_fraction,
    live_projected_points,
)


def test_live_projection_decreases_when_a_player_is_behind_pace_midgame():
    projection, source, progress = live_projected_points(
        pre_game_projection=20.0,
        actual_points=3.0,
        lifecycle_state="live",
        provider_payload={"status": {"period": 2, "displayClock": "7:30"}},
    )

    assert progress == pytest.approx(0.375)
    assert projection == pytest.approx(15.5)
    assert source == "live_pace_adjusted"


def test_final_uses_actual_points_and_preserves_the_pre_game_projection_for_display():
    projection, source, progress = live_projected_points(
        pre_game_projection=20.0,
        actual_points=8.0,
        lifecycle_state="final",
        provider_payload={"status": {"period": 4, "displayClock": "0:00"}},
    )

    assert projection == 8.0
    assert source == "actual"
    assert progress == 1.0


def test_active_game_without_espn_clock_uses_a_conservative_midpoint():
    assert game_progress_fraction(lifecycle_state="live", provider_payload={}) == 0.5

