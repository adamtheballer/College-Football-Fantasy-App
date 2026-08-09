import hashlib
import json

import pytest

from scripts.import_preseason_weekly_projections import _require_inputs, _stats


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


def test_kicker_without_distance_buckets_and_missing_baseline_are_not_scored():
    assert _stats({**_annual(), "POSITION": "K", "FG": "22"}, 12) is None
    assert _stats({**_annual(), "RUSH YDS": ""}, 12) is None


def test_builder_requires_complete_matching_sealed_manifest_and_scoring_audit(tmp_path):
    annual = tmp_path / "annual.csv"; annual.write_text("x\n", encoding="utf-8")
    schedule = tmp_path / "schedule.csv"; schedule.write_text("x\n", encoding="utf-8")
    annual_hash = hashlib.sha256(annual.read_bytes()).hexdigest()
    schedule_hash = hashlib.sha256(schedule.read_bytes()).hexdigest()
    names = ["player_id_details", "team_rankings", "player_previous_stats", "annual_projections", "schedules", "cfb27_ratings"]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"snapshots": [{"workbook": name, "sha256": annual_hash if name == "annual_projections" else schedule_hash if name == "schedules" else name} for name in names]}), encoding="utf-8")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"policy_name": "component_stats_canonical_scoring_v1", "source_sha256": annual_hash}), encoding="utf-8")
    assert _require_inputs(manifest, annual, schedule, audit)[0] == annual_hash
    audit.write_text(json.dumps({"policy_name": "wrong", "source_sha256": annual_hash}), encoding="utf-8")
    with pytest.raises(ValueError, match="policy"):
        _require_inputs(manifest, annual, schedule, audit)
