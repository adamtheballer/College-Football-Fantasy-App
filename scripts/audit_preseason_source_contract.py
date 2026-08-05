"""Validate the reviewed preseason player sources before an import can run.

The player-ID/bio snapshot is the canonical public-player allow-list.  A player
can receive a preseason projection only when the corresponding reviewed
identity row exists, and every reviewed identity must have a seasonal
projection.  This script is deliberately dependency-light so release jobs can
fail before touching the database.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIRECTORY = ROOT_DIR / "reports" / "source-imports" / "2026"
SUPPORTED_POSITIONS = ("QB", "RB", "WR", "TE", "K")
IDENTITY_SPREADSHEET_ID = "1yssIYnzIAImmPOSkFqZQAn1i54CZ3aKzMlzGyvgvrlQ"
PROJECTION_SPREADSHEET_ID = "1NMP3EJSMbdRd7HDA0t7TwxzJ9DM_bUynLoRCgE6Ml74"
RECONCILIATION_ARTIFACT_DIR = ROOT_DIR / "artifacts" / "reconciliation"
SOURCE_MANIFEST_FILENAME = "source-manifest.json"
SOURCE_MANIFEST_SCHEMA_VERSION = 1
SOURCE_MANIFEST_SEASON = 2026
SOURCE_MANIFEST_SOURCES = {
    "identity": {
        "file": "player-identities.csv",
        "spreadsheet_id": IDENTITY_SPREADSHEET_ID,
        "tabs": ("Big 10", "ACC", "SEC", "Big 12", "Notre Dame"),
    },
    "projection": {
        "file": "player-projections.csv",
        "spreadsheet_id": PROJECTION_SPREADSHEET_ID,
        "tabs": ("Big10", "ACC", "SEC", "Big12", "Notre Dame"),
    },
}

# This is a release-data integrity assertion, not a player-specific runtime
# fallback. It pins a reviewed source row whose projection is used to catch a
# season/weekly lineage mix-up before any reconciliation can touch a database.
WAYNE_KNIGHT_EXPECTED_PROJECTION = {
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
WAYNE_KNIGHT_APPROVED_SOURCE_BATCH = "2026-08-05-live-sheets-r361-r923-r347-refresh-043626z"
WAYNE_KNIGHT_APPROVED_PROJECTION_SNAPSHOT_SHA256 = "49d0c74db64ae2fa37ef42d4f55fa0eba1c9ba8abfef523d2828a43265dbc5d3"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from collegefootballfantasy_api.app.services.power4 import normalize_school, resolve_power4_school


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(value: str | None) -> float | None:
    try:
        return float((value or "").replace(",", ""))
    except ValueError:
        return None


def _normal(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _position(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    return next((position for position in SUPPORTED_POSITIONS if normalized.startswith(position)), None)


def _team(value: str | None) -> str | None:
    """Normalize a reviewed player school without importing a runtime-only sync module.

    The release audit must run from the published artifact.  Keeping the
    school rule here aligned with the approved fantasy-pool rule avoids a
    hidden dependency on untracked projection code.  Notre Dame is the sole
    intentional non-Power-4 exception in the source workbook.
    """

    raw = (value or "").strip()
    if not raw:
        return None
    if normalize_school(raw) == normalize_school("Notre Dame"):
        return "Notre Dame"
    return resolve_power4_school(raw) or raw


def _key(name: str | None, school: str | None, position: str | None) -> tuple[str, str, str]:
    return _normal(name), _normal(school), position or ""


def _display(key: tuple[str, str, str]) -> str:
    name, school, position = key
    return f"{name or '<blank>'} | {school or '<blank>'} | {position or '<blank>'}"


def audit_rows(
    projection_rows: list[dict[str, str]], identity_rows: list[dict[str, str]]
) -> dict[str, Any]:
    projection_keys = [
        _key(row.get("PLAYER"), _team(row.get("TEAM")), _position(row.get("POSITION")))
        for row in projection_rows
    ]
    identity_keys = [
        _key(row.get("NAME"), _team(row.get("SCHOOL")), _position(row.get("POSITION")))
        for row in identity_rows
    ]
    invalid_projection_rows = [index + 2 for index, key in enumerate(projection_keys) if not all(key)]
    invalid_identity_rows = [index + 2 for index, key in enumerate(identity_keys) if not all(key)]
    unique_projection_keys = set(projection_keys)
    unique_identity_keys = set(identity_keys)
    projection_only = sorted(unique_projection_keys - unique_identity_keys)
    identity_only = sorted(unique_identity_keys - unique_projection_keys)
    return {
        "status": "PASS"
        if not (invalid_projection_rows or invalid_identity_rows or len(unique_projection_keys) != len(projection_keys)
                or len(unique_identity_keys) != len(identity_keys) or projection_only or identity_only)
        else "FAIL",
        "projection_rows": len(projection_rows),
        "identity_rows": len(identity_rows),
        "approved_player_count": len(unique_projection_keys.intersection(unique_identity_keys)),
        "projection_duplicate_count": len(projection_keys) - len(unique_projection_keys),
        "identity_duplicate_count": len(identity_keys) - len(unique_identity_keys),
        "invalid_projection_row_numbers": invalid_projection_rows,
        "invalid_identity_row_numbers": invalid_identity_rows,
        "projection_rows_without_identity_count": len(projection_only),
        "identity_rows_without_projection_count": len(identity_only),
        "projection_rows_without_identity": [_display(key) for key in projection_only],
        "identity_rows_without_projection": [_display(key) for key in identity_only],
    }


def wayne_knight_projection_integrity(
    projection_rows: list[dict[str, str]], identity_rows: list[dict[str, str]]
) -> dict[str, Any]:
    """Verify one reviewed release sentinel across identity and projection rows."""

    expected = WAYNE_KNIGHT_EXPECTED_PROJECTION
    key = _key(expected["name"], expected["team"], expected["position"])
    projection_matches = [
        (row_number, row)
        for row_number, row in enumerate(projection_rows, start=2)
        if _key(row.get("PLAYER"), _team(row.get("TEAM")), _position(row.get("POSITION"))) == key
    ]
    identity_matches = [
        (row_number, row)
        for row_number, row in enumerate(identity_rows, start=2)
        if _key(row.get("NAME"), _team(row.get("SCHOOL")), _position(row.get("POSITION"))) == key
    ]
    errors: list[str] = []
    if len(projection_matches) != 1:
        errors.append(f"Wayne Knight must resolve to exactly one projection row; found {len(projection_matches)}.")
    if len(identity_matches) != 1:
        errors.append(f"Wayne Knight must resolve to exactly one identity row; found {len(identity_matches)}.")

    projection_row = projection_matches[0][1] if len(projection_matches) == 1 else None
    identity_row = identity_matches[0][1] if len(identity_matches) == 1 else None
    if projection_row is not None:
        if (projection_row.get("POSITION") or "").strip().upper() != expected["depth_role"]:
            errors.append("Wayne Knight projection row must retain the reviewed RB1 depth role.")
        for source_column, expected_value in {
            "RUSH YDS": expected["rush_yards"],
            "RUSH TDS": expected["rush_tds"],
            "RECEPTIONS": expected["receptions"],
            "REC YDS": expected["rec_yards"],
            "REC TDS": expected["rec_tds"],
            "FANTASY PROJ.": expected["fantasy_points"],
        }.items():
            if _number(projection_row.get(source_column)) != expected_value:
                errors.append(
                    f"Wayne Knight projection {source_column!r} must equal {expected_value:g}, got {projection_row.get(source_column)!r}."
                )
    if identity_row is not None and (identity_row.get("POSITION") or "").strip().upper() != expected["depth_role"]:
        errors.append("Wayne Knight identity row must retain the reviewed RB1 depth role.")

    return {
        "status": "PASS" if not errors else "FAIL",
        "canonical_key": _display(key),
        "identity_source_row": identity_matches[0][0] if len(identity_matches) == 1 else None,
        "projection_source_row": projection_matches[0][0] if len(projection_matches) == 1 else None,
        "projection": expected,
        "provider_id": projection_row.get("PROVIDER ID") if projection_row else None,
        "errors": errors,
    }


def _source_fingerprint(path: Path) -> dict[str, str]:
    contents = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(contents).hexdigest(),
        "exported_at_utc": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
        "bytes": str(len(contents)),
    }


def _parse_utc_timestamp(value: Any) -> bool:
    """Return whether a manifest timestamp is explicit and timezone-aware."""

    if not isinstance(value, str) or not value.strip():
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _source_provenance(source_dir: Path, *, require_manifest: bool) -> dict[str, Any]:
    """Validate that both release inputs came from one identified source batch.

    File mtimes are useful diagnostics but are not evidence that two CSV exports
    came from the same Sheets revision.  A release snapshot therefore needs a
    checked-in manifest whose per-source hash, Drive revision identifier, and
    shared export batch ID can be verified before it is treated as authoritative.
    """

    manifest_path = source_dir / SOURCE_MANIFEST_FILENAME
    result: dict[str, Any] = {
        "required": require_manifest,
        "status": "PASS" if not require_manifest else "FAIL",
        "manifest_path": str(manifest_path),
        "errors": [],
        "export_batch_id": "",
        "sources": {},
    }
    if not manifest_path.is_file():
        if require_manifest:
            result["errors"].append(
                "Missing source-manifest.json. Local file timestamps cannot prove these identity and projection exports came from one approved Sheets revision."
            )
        else:
            result["status"] = "UNVERIFIED"
            result["errors"].append(
                "No source manifest was supplied for this non-release fixture; provenance is intentionally unverified."
            )
        return result

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        result["errors"].append(f"Could not parse source manifest: {error}")
        return result
    if not isinstance(manifest, dict):
        result["errors"].append("Source manifest root must be a JSON object.")
        return result
    if manifest.get("schema_version") != SOURCE_MANIFEST_SCHEMA_VERSION:
        result["errors"].append(
            f"Unsupported source manifest schema_version {manifest.get('schema_version')!r}; expected {SOURCE_MANIFEST_SCHEMA_VERSION}."
        )
    if manifest.get("season") != SOURCE_MANIFEST_SEASON:
        result["errors"].append(
            f"Source manifest season {manifest.get('season')!r} does not match required season {SOURCE_MANIFEST_SEASON}."
        )
    batch_id = manifest.get("export_batch_id")
    if not isinstance(batch_id, str) or not batch_id.strip():
        result["errors"].append("Source manifest requires one non-empty export_batch_id shared by both exports.")
    else:
        result["export_batch_id"] = batch_id.strip()
    sources = manifest.get("sources")
    if not isinstance(sources, dict):
        result["errors"].append("Source manifest requires a sources object.")
        sources = {}

    for source_name, expected in SOURCE_MANIFEST_SOURCES.items():
        actual = sources.get(source_name)
        if not isinstance(actual, dict):
            result["errors"].append(f"Source manifest is missing the {source_name!r} source entry.")
            continue
        result["sources"][source_name] = actual
        if actual.get("spreadsheet_id") != expected["spreadsheet_id"]:
            result["errors"].append(
                f"{source_name} spreadsheet_id does not match the configured authoritative source."
            )
        if actual.get("snapshot_file") != expected["file"]:
            result["errors"].append(
                f"{source_name} snapshot_file must be {expected['file']!r}."
            )
        actual_tabs = actual.get("tabs")
        if not isinstance(actual_tabs, list) or tuple(actual_tabs) != expected["tabs"]:
            result["errors"].append(
                f"{source_name} tabs must exactly match the configured authoritative tab order."
            )
        if not _parse_utc_timestamp(actual.get("exported_at_utc")):
            result["errors"].append(
                f"{source_name} exported_at_utc must be a timezone-aware ISO-8601 timestamp."
            )
        revision = actual.get("spreadsheet_revision")
        if not isinstance(revision, str) or not revision.strip():
            result["errors"].append(
                f"{source_name} spreadsheet_revision is required; do not infer a Sheets revision from the CSV mtime."
            )
        snapshot_path = source_dir / expected["file"]
        expected_sha256 = actual.get("sha256")
        actual_sha256 = _source_fingerprint(snapshot_path)["sha256"] if snapshot_path.is_file() else "MISSING"
        if expected_sha256 != actual_sha256:
            result["errors"].append(
                f"{source_name} snapshot SHA-256 does not match the manifest (expected {expected_sha256!r}, got {actual_sha256!r})."
            )

    if result["errors"]:
        return result
    result["status"] = "PASS"
    return result


def _strict_discrepancies(
    rows: list[dict[str, str]], *, side: str, other_keys: set[tuple[str, str, str]]
) -> list[dict[str, str | int]]:
    output: list[dict[str, str | int]] = []
    name_column, school_column = ("NAME", "SCHOOL") if side == "identity" else ("PLAYER", "TEAM")
    for row_number, row in enumerate(rows, start=2):
        key = _key(row.get(name_column), _team(row.get(school_column)), _position(row.get("POSITION")))
        if key not in other_keys:
            output.append(
                {
                    "side": side,
                    "source_sheet": row.get("source_sheet", ""),
                    "row_number": row_number,
                    "school": row.get(school_column, ""),
                    "position": row.get("POSITION", ""),
                    "name": row.get(name_column, ""),
                    "normalized_key": _display(key),
                    "reason": "NO_EXACT_COMPOSITE_MATCH",
                }
            )
    return output


def audit_source_directory(source_dir: Path, *, require_provenance: bool | None = None) -> dict[str, Any]:
    """Run the strict release contract with reproducibility evidence.

    This remains intentionally stricter than the reconciliation report: it does
    not accept similarity candidates or implicit aliases beyond the approved
    school resolver. A failing return therefore blocks all publishing commands.
    """

    source_dir = source_dir.resolve()
    if require_provenance is None:
        require_provenance = source_dir == DEFAULT_SOURCE_DIRECTORY.resolve()
    projection_path = source_dir / "player-projections.csv"
    identity_path = source_dir / "player-identities.csv"
    projection_rows = _read_csv(projection_path)
    identity_rows = _read_csv(identity_path)
    report = audit_rows(projection_rows, identity_rows)
    wayne_integrity = wayne_knight_projection_integrity(projection_rows, identity_rows)
    provenance = _source_provenance(source_dir, require_manifest=require_provenance)
    if provenance["status"] == "FAIL":
        report["status"] = "FAIL"
    projection_keys = {
        _key(row.get("PLAYER"), _team(row.get("TEAM")), _position(row.get("POSITION")))
        for row in projection_rows
    }
    identity_keys = {
        _key(row.get("NAME"), _team(row.get("SCHOOL")), _position(row.get("POSITION")))
        for row in identity_rows
    }
    strict_discrepancies = _strict_discrepancies(identity_rows, side="identity", other_keys=projection_keys) + _strict_discrepancies(
        projection_rows, side="projection", other_keys=identity_keys
    )
    by_conference = Counter(
        f"{item['side']}:{item['source_sheet']}" for item in strict_discrepancies
    )
    by_reason = Counter(item["reason"] for item in strict_discrepancies)
    bootstrap_path = ROOT_DIR / "scripts" / "bootstrap_canonical_player_data.py"
    report["gate_context"] = {
        "identity_spreadsheet_id": IDENTITY_SPREADSHEET_ID,
        "projection_spreadsheet_id": PROJECTION_SPREADSHEET_ID,
        "identity_export": _source_fingerprint(identity_path),
        "projection_export": _source_fingerprint(projection_path),
        "canonical_bootstrap_version_sha256": (
            hashlib.sha256(bootstrap_path.read_bytes()).hexdigest() if bootstrap_path.exists() else "MISSING"
        ),
        "identity_dataset_version": f"2026:{_source_fingerprint(identity_path)['sha256'][:12]}",
        "projection_dataset_version": f"2026:{_source_fingerprint(projection_path)['sha256'][:12]}",
        "source_provenance": provenance,
        "unmatched_count_by_conference": dict(sorted(by_conference.items())),
        "unmatched_count_by_reason": dict(sorted(by_reason.items())),
        "first_20_discrepancies": strict_discrepancies[:20],
        "reconciliation_artifacts": {
            "csv": str(RECONCILIATION_ARTIFACT_DIR / "player-source-reconciliation.csv"),
            "json": str(RECONCILIATION_ARTIFACT_DIR / "player-source-reconciliation.json"),
            "summary": str(RECONCILIATION_ARTIFACT_DIR / "player-source-summary.md"),
        },
        "note": "The strict contract never consumes similarity suggestions. Reconciliation artifacts are review evidence only and cannot unblock the release until sources or approved overrides resolve every discrepancy. A release source directory additionally requires a verified shared-batch manifest; local mtimes are diagnostics, not source-revision evidence.",
    }
    wayne_integrity["source_batch_id"] = provenance.get("export_batch_id")
    wayne_integrity["projection_snapshot_sha256"] = provenance.get("sources", {}).get("projection", {}).get("sha256")
    if wayne_integrity["source_batch_id"] != WAYNE_KNIGHT_APPROVED_SOURCE_BATCH:
        wayne_integrity["errors"].append(
            "Wayne Knight must be reconciled from the approved shared source batch."
        )
    if wayne_integrity["projection_snapshot_sha256"] != WAYNE_KNIGHT_APPROVED_PROJECTION_SNAPSHOT_SHA256:
        wayne_integrity["errors"].append(
            "Wayne Knight must be reconciled from the approved projection snapshot hash."
        )
    if wayne_integrity["errors"]:
        wayne_integrity["status"] = "FAIL"
    report["wayne_knight_projection_integrity"] = wayne_integrity
    if wayne_integrity["status"] != "PASS":
        report["status"] = "FAIL"
    return report


class PreseasonSourceContractError(ValueError):
    """Raised before a database import when reviewed player sources disagree."""


def _contract_error_message(report: dict[str, Any]) -> str:
    """Build one actionable rejection reason for every importing command."""

    message = (
        "reviewed player-ID and seasonal-projection snapshots disagree: "
        f"{report['identity_rows_without_projection_count']} identity row(s) have no matching seasonal projection; "
        f"{report['projection_rows_without_identity_count']} projection row(s) have no matching identity; "
        f"{report['identity_duplicate_count']} duplicate identity key(s); "
        f"{report['projection_duplicate_count']} duplicate projection key(s); "
        f"{len(report['invalid_identity_row_numbers'])} invalid identity row(s); and "
        f"{len(report['invalid_projection_row_numbers'])} invalid projection row(s)."
    )
    provenance = report.get("gate_context", {}).get("source_provenance", {})
    provenance_errors = provenance.get("errors", []) if isinstance(provenance, dict) else []
    if provenance_errors:
        message += " Source provenance also failed: " + " ".join(str(error) for error in provenance_errors)
    return message + " Fix the reviewed source snapshots; do not publish a partial, inferred, or unversioned draft pool."


def require_valid_source_directory(
    source_dir: Path, *, require_provenance: bool = True
) -> dict[str, Any]:
    """Reject imports unless a complete, versioned source directory passes.

    ``require_valid_contract`` protects callers that already have in-memory
    rows.  Database-mutating command-line jobs must use this stronger entry
    point instead so they cannot skip the shared-export provenance check.
    """

    report = audit_source_directory(source_dir, require_provenance=require_provenance)
    if report["status"] == "PASS":
        return report
    raise PreseasonSourceContractError(_contract_error_message(report))


def require_valid_contract(
    projection_rows: list[dict[str, str]], identity_rows: list[dict[str, str]]
) -> dict[str, Any]:
    """Return the source report or stop an import before it can mutate data.

    Every command that can publish the preseason player universe must use this
    one guard.  Keeping the failure rule here prevents bootstrap and weekly
    sync scripts from drifting into different definitions of the public pool.
    """

    report = audit_rows(projection_rows, identity_rows)
    if report["status"] == "PASS":
        return report
    raise PreseasonSourceContractError(_contract_error_message(report))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate reviewed player-ID and seasonal-projection source snapshots.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIRECTORY)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_source_directory(args.source_dir)
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
