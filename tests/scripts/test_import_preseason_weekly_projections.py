import hashlib
import json

import pytest

from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from scripts.import_preseason_weekly_projections import _canonical_source_team, _require_inputs, _stats


def _annual() -> dict[str, str]:
    return {
        "POSITION": "RB1", "ATTEMPTS": "0", "RECEPTIONS": "28", "PASS YDS": "0", "PASS TDS": "0",
        "INTS": "0", "RUSH YDS": "1428", "RUSH TDS": "14", "REC YDS": "244", "REC TDS": "2", "XP": "0", "FG": "0",
    }


def test_kewan_neutral_weekly_components_preserve_source_math():
    values = _stats(_annual(), 12)
    assert values is not None
    assert values["rush_yards"] == 119
    assert values["receptions"] == pytest.approx(28 / 12)
    points, _ = calculate_player_fantasy_points(
        {
            "pass_yards": values["pass_yards"], "pass_tds": values["pass_tds"],
            "interceptions": values["interceptions"], "rush_yards": values["rush_yards"],
            "rush_tds": values["rush_tds"], "receptions": values["receptions"],
            "rec_yards": values["rec_yards"], "rec_tds": values["rec_tds"],
            "xp_made": values["extra_points_made"],
        }, {}, "RB",
    )
    assert 291.2 / 12 == pytest.approx(24.2666666667)
    # The canonical engine intentionally stores its scored output at its
    # established two-decimal precision after receiving unrounded components.
    assert points == 24.27


def test_weekly_projection_scoring_deducts_interceptions():
    values = _stats({**_annual(), "POSITION": "QB", "PASS YDS": "0", "PASS TDS": "0", "INTS": "24", "RUSH YDS": "0", "RUSH TDS": "0", "RECEPTIONS": "0", "REC YDS": "0", "REC TDS": "0"}, 12)

    assert values is not None
    points, _ = calculate_player_fantasy_points(
        {"interceptions": values["interceptions"]}, {}, "QB"
    )
    assert points == -4.0


def test_kicker_total_field_goals_uses_flat_beta_scoring_and_missing_baseline_is_rejected():
    values = _stats({**_annual(), "POSITION": "K", "FG": "22", "XP": "30"}, 12)
    assert values is not None
    points, _ = calculate_player_fantasy_points(
        {"fg_made_0_30": values["field_goals_made_0_to_39"], "xp_made": values["extra_points_made"]},
        {"fg_made_0_30": 3, "fg_made_31_40": 3, "fg_made_41_50": 3, "fg_made_51_60": 3, "fg_made_61_plus": 3, "xp_made": 1},
        "K",
    )
    assert points == pytest.approx((22 * 3 + 30) / 12)
    assert _stats({**_annual(), "RUSH YDS": ""}, 12) is None


def test_canonical_source_team_keeps_notre_dame_consistent_between_workbooks():
    assert _canonical_source_team("NOTRE DAME") == "Notre Dame"
    assert _canonical_source_team("Notre Dame") == "Notre Dame"


def test_builder_requires_complete_matching_sealed_manifest_and_scoring_audit(tmp_path):
    annual = tmp_path / "annual.csv"; annual.write_text("x\n", encoding="utf-8")
    schedule = tmp_path / "schedule.csv"; schedule.write_text("x\n", encoding="utf-8")
    annual_hash = hashlib.sha256(annual.read_bytes()).hexdigest()
    schedule_hash = hashlib.sha256(schedule.read_bytes()).hexdigest()
    names = ["player_id_details", "team_rankings", "player_previous_stats", "annual_projections", "schedules", "cfb27_ratings"]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"snapshots": [{"workbook": name, "sha256": annual_hash if name == "annual_projections" else schedule_hash if name == "schedules" else name} for name in names]}), encoding="utf-8")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"policy_name": "component_stats_canonical_scoring_v2_beta_flat_kicker", "source_sha256": annual_hash}), encoding="utf-8")
    assert _require_inputs(manifest, annual, schedule, audit)[0] == annual_hash
    audit.write_text(json.dumps({"policy_name": "wrong", "source_sha256": annual_hash}), encoding="utf-8")
    with pytest.raises(ValueError, match="policy"):
        _require_inputs(manifest, annual, schedule, audit)
