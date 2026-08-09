import json
import shutil
from pathlib import Path

from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from scripts.audit_preseason_source_contract import (
    DEFAULT_SOURCE_DIRECTORY,
    audit_source_directory,
    require_valid_source_directory,
)


def _copied_snapshot(tmp_path: Path) -> Path:
    destination = tmp_path / "source-imports" / "2026"
    shutil.copytree(DEFAULT_SOURCE_DIRECTORY, destination)
    return destination


def test_checked_in_snapshot_is_a_complete_814_player_release_input():
    report = audit_source_directory(DEFAULT_SOURCE_DIRECTORY, require_provenance=True)

    assert report["status"] == "PASS"
    assert report["identity_rows"] == 814
    assert report["projection_rows"] == 814
    assert report["approved_player_count"] == 814
    assert report["gate_context"]["source_provenance"]["status"] == "PASS"


def test_wayne_knight_projection_integrity_is_bound_to_the_manifested_batch():
    report = audit_source_directory(DEFAULT_SOURCE_DIRECTORY, require_provenance=True)
    wayne = report["wayne_knight_projection_integrity"]

    assert wayne["status"] == "PASS"
    assert wayne["identity_source_row"] == 171
    assert wayne["projection_source_row"] == 171
    assert wayne["projection"] == {
        "name": "Wayne Knight",
        "team": "UCLA",
        "position": "RB",
        "depth_role": "RB1",
        "rush_yards": 1300.0,
        "rush_tds": 12.0,
        "receptions": 28.0,
        "rec_yards": 230.0,
        "rec_tds": 2.0,
        "fantasy_points": 265.0,
    }
    provenance = report["gate_context"]["source_provenance"]
    assert wayne["source_batch_id"] == provenance["export_batch_id"]
    assert wayne["projection_snapshot_sha256"] == provenance["sources"]["projection"]["sha256"]


def test_wayne_knight_gate_rejects_a_manifest_with_a_tampered_projection_hash(tmp_path: Path):
    snapshot_dir = _copied_snapshot(tmp_path)
    manifest_path = snapshot_dir / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"]["projection"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = audit_source_directory(snapshot_dir, require_provenance=True)

    assert report["status"] == "FAIL"
    assert report["gate_context"]["source_provenance"]["status"] == "FAIL"
    assert any(
        "projection snapshot SHA-256 does not match the manifest" in error
        for error in report["gate_context"]["source_provenance"]["errors"]
    )


def test_wayne_knight_accepts_a_later_manifested_batch_when_source_bytes_are_valid(tmp_path: Path):
    snapshot_dir = _copied_snapshot(tmp_path)
    manifest_path = snapshot_dir / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["export_batch_id"] = "2026-08-09-approved-later-export"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = audit_source_directory(snapshot_dir, require_provenance=True)

    assert report["status"] == "PASS"
    assert report["wayne_knight_projection_integrity"]["status"] == "PASS"
    assert report["wayne_knight_projection_integrity"]["source_batch_id"] == "2026-08-09-approved-later-export"


def test_wayne_knight_source_stats_calculate_to_265_under_the_approved_default_rules():
    total, breakdown = calculate_player_fantasy_points(
        {
            "rush_yards": 1300,
            "rush_tds": 12,
            "receptions": 28,
            "rec_yards": 230,
            "rec_tds": 2,
        },
        {},
        "RB",
    )

    assert breakdown["rush_yards"]["points"] == 130.0
    assert breakdown["rush_tds"]["points"] == 72.0
    assert breakdown["receptions"]["points"] == 28.0
    assert breakdown["rec_yards"]["points"] == 23.0
    assert breakdown["rec_tds"]["points"] == 12.0
    assert total == 265.0


def test_snapshot_hash_tampering_blocks_the_release_gate(tmp_path: Path):
    snapshot_dir = _copied_snapshot(tmp_path)
    with (snapshot_dir / "player-identities.csv").open("a", encoding="utf-8") as handle:
        handle.write("# tampered\n")

    report = audit_source_directory(snapshot_dir, require_provenance=True)

    assert report["status"] == "FAIL"
    assert any(
        "identity snapshot SHA-256 does not match the manifest" in error
        for error in report["gate_context"]["source_provenance"]["errors"]
    )


def test_release_import_rejects_an_unmanifested_snapshot(tmp_path: Path):
    snapshot_dir = _copied_snapshot(tmp_path)
    (snapshot_dir / "source-manifest.json").unlink()

    try:
        require_valid_source_directory(snapshot_dir)
    except ValueError as error:
        assert "Source provenance also failed" in str(error)
    else:
        raise AssertionError("An unmanifested source directory must not be importable.")
