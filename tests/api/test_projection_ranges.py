from collegefootballfantasy_api.app.services.projections.ranges import weighted_projection_outcomes


def test_weighted_projection_range_couples_floor_ceiling_and_tail_percentages() -> None:
    outcomes = weighted_projection_outcomes(
        20.0,
        position="RB",
        expected_opportunities=18.0,
    )

    # The values are calculated from one weighted distribution rather than
    # independent display heuristics.
    assert outcomes.floor == 13.6
    assert outcomes.ceiling == 27.0
    assert outcomes.boom_prob == 0.1223
    assert outcomes.bust_prob == 0.1437


def test_low_volume_role_has_a_wider_and_riskier_outcome_range() -> None:
    high_volume = weighted_projection_outcomes(20.0, position="RB", expected_opportunities=18.0)
    low_volume = weighted_projection_outcomes(20.0, position="RB", expected_opportunities=4.0)

    assert low_volume.floor < high_volume.floor
    assert low_volume.ceiling > high_volume.ceiling
    assert low_volume.boom_prob > high_volume.boom_prob
    assert low_volume.bust_prob > high_volume.bust_prob


def test_zero_projection_has_no_artificial_range_or_tail_probability() -> None:
    assert weighted_projection_outcomes(0.0, position="WR") == weighted_projection_outcomes(
        None,
        position="WR",
    )
