import shutil
from pathlib import Path

from scripts.audit_preseason_source_contract import (
    DEFAULT_SOURCE_DIRECTORY,
    audit_source_directory,
    require_valid_source_directory,
)


def _copied_snapshot(tmp_path: Path) -> Path:
    destination = tmp_path / "source-imports" / "2026"
    shutil.copytree(DEFAULT_SOURCE_DIRECTORY, destination)
    return destination


def test_checked_in_snapshot_is_a_complete_813_player_release_input():
    report = audit_source_directory(DEFAULT_SOURCE_DIRECTORY, require_provenance=True)

    assert report["status"] == "PASS"
    assert report["identity_rows"] == 813
    assert report["projection_rows"] == 813
    assert report["approved_player_count"] == 813
    assert report["gate_context"]["source_provenance"]["status"] == "PASS"


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
