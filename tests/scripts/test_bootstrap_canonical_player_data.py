import pytest

from scripts.bootstrap_canonical_player_data import projection_stats_for_row


def _projection(**overrides: str) -> dict[str, str]:
    row = {
        "PLAYER": "Kewan Lacy", "TEAM": "OLE MISS", "POSITION": "RB1",
        "COMP.": "0", "ATTEMPTS": "0", "PASS YDS": "0", "PASS TDS": "0", "INTS": "0",
        "RUSH YDS": "1428", "RUSH TDS": "14", "RECEPTIONS": "28", "REC YDS": "244",
        "REC TDS": "2", "FG": "0", "XP": "0", "FANTASY PROJ.": "322.2",
    }
    row.update(overrides)
    return row


def test_bootstrap_uses_component_derived_fantasy_points_not_raw_sheet_total():
    stats = projection_stats_for_row(_projection())

    assert stats["fpts"] == 291.2
    assert stats["source_fantasy_proj"] == 322.2
    assert stats["scoring_policy_version"] == "component_stats_canonical_scoring_v2_beta_flat_kicker"


def test_bootstrap_scores_kicker_total_with_flat_beta_rules():
    stats = projection_stats_for_row(_projection(POSITION="K", **{"FG": "22", "XP": "30"}))

    assert stats["fpts"] == 96
