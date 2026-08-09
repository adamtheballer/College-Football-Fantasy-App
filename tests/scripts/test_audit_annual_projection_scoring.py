from scripts.audit_annual_projection_scoring import audit


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "PLAYER": "Kewan Lacy", "TEAM": "OLE MISS", "POSITION": "RB1",
        "PASS YDS": "0", "PASS TDS": "0", "INTS": "0", "RUSH YDS": "1428",
        "RUSH TDS": "14", "RECEPTIONS": "28", "REC YDS": "244", "REC TDS": "2",
        "XP": "0", "FG": "0", "FANTASY PROJ.": "322.2",
    }
    row.update(overrides)
    return row


def test_audit_proves_kewan_lacy_sheet_total_does_not_match_canonical_scoring():
    report = audit([_row()])

    assert report["exact_matches"] == 0
    assert report["mismatches"] == 1
    finding = report["review_required"][0]
    assert finding["canonical_fantasy_points"] == 291.2
    assert finding["difference_canonical_minus_sheet"] == -31.0
    assert finding["reason"] == "unproven_scoring_rule_difference"


def test_audit_refuses_to_score_kicker_total_without_distance_buckets():
    report = audit([_row(PLAYER="K", POSITION="K", FG="24", XP="30", **{"FANTASY PROJ.": "102"})])

    assert report["outcome_counts"] == {"UNSCORABLE_KICKER_DISTANCE": 1}
    assert report["review_required"][0]["canonical_fantasy_points"] is None


def test_audit_identifies_exact_match_and_missing_component_separately():
    report = audit([_row(**{"FANTASY PROJ.": "291.2"}), _row(PLAYER="Blank", **{"REC YDS": ""})])

    assert report["outcome_counts"] == {"EXACT_MATCH": 1, "MISSING_COMPONENT": 1}


def test_audit_keeps_invalid_and_unmatched_rows_separate_from_missing_components():
    report = audit([
        _row(PLAYER="", **{"FANTASY PROJ.": "291.2"}),
        _row(PLAYER="Invalid", **{"RUSH YDS": "not-a-number"}),
    ])

    assert report["outcome_counts"] == {"INVALID_COMPONENT": 1, "UNMATCHED_PLAYER": 1}
    assert report["review_required"][0]["source_row"] == 2
    assert "canonical_player_identity" in report["review_required"][0]
