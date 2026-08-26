from collegefootballfantasy_api.app.services.injury_value import (
    SHORT_ABSENCE_VALUE_MULTIPLIER,
    estimated_absence_weeks,
    injury_value_multiplier,
)


def test_duration_aware_injury_value_policy_uses_the_upper_range_bound():
    assert estimated_absence_weeks("2-4 weeks") == 4
    assert injury_value_multiplier("OUT", return_timeline="2-4 weeks") == SHORT_ABSENCE_VALUE_MULTIPLIER
    assert injury_value_multiplier("OUT", return_timeline="1 week") == 0.82
    assert injury_value_multiplier("OUT", return_timeline="6 weeks") == 0.58
    assert injury_value_multiplier("OUT FOR SEASON") == 0.30


def test_returning_short_term_players_recover_to_ninety_percent():
    assert injury_value_multiplier("FULL", is_returning=True) == 0.90
    assert injury_value_multiplier("ACTIVE") == 1.0
