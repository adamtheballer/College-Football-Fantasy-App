import pytest

from scripts.import_preseason_weekly_projections import sealed_annual_baseline_source
from scripts.publish_preseason_weekly_projections import parse_args


def test_publisher_accepts_the_same_annual_source_provenance_stored_by_importer():
    annual_hash = "0b3d244603cd0000000000000000000000000000000000000000000000000000"

    # Production PRESEASON rows are tagged from the sealed annual projection
    # workbook.  The publisher must not compare them to the unrelated bundle
    # manifest hash.
    assert sealed_annual_baseline_source(annual_hash) == "sealed:0b3d244603cd"


def test_publisher_provenance_refuses_a_non_sha_value():
    with pytest.raises(ValueError, match="SHA-256"):
        sealed_annual_baseline_source("manifest-name-is-not-a-hash")


def test_publisher_requires_the_annual_projection_hash_not_an_umbrella_manifest(tmp_path):
    annual_hash = "0b3d244603cd0000000000000000000000000000000000000000000000000000"

    args = parse_args(
        [
            "--season", "2026",
            "--week", "1",
            "--annual-source-hash", annual_hash,
            "--player-id", "1070",
            "--report", str(tmp_path / "publication.json"),
        ]
    )

    assert args.annual_source_hash == annual_hash
