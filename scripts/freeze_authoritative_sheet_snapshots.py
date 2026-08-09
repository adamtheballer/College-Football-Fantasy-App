#!/usr/bin/env python3
"""Create one immutable manifest from authenticated Sheet exports.

This intentionally has no Google API client.  The release operator exports the
approved tabs through authenticated Google Drive into a non-repository staging
directory, then this command copies and hashes those exact bytes.  Importers
only accept the sealed output; they never read a mutable Sheet URL.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path


PARSER_VERSION = "authoritative-sheet-freeze-v1"
DEFAULT_OUTPUT_ROOT = Path("reports/source-imports/2026/authoritative-snapshots")
REQUIRED_WORKBOOKS = frozenset({
    "player_id_details",
    "team_rankings",
    "player_previous_stats",
    "annual_projections",
    "schedules",
    "cfb27_ratings",
})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nonempty_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return sum(bool(any(cell.strip() for cell in row)) for row in csv.reader(handle))


def _validate_file(path: Path) -> int | None:
    if path.suffix.lower() == ".csv":
        try:
            return _nonempty_rows(path)
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise ValueError(f"Malformed CSV export {path.name}: {exc}") from exc
    if path.suffix.lower() == ".xlsx":
        try:
            with zipfile.ZipFile(path) as archive:
                if "[Content_Types].xml" not in archive.namelist():
                    raise ValueError("missing XLSX content-types document")
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            raise ValueError(f"Malformed XLSX export {path.name}: {exc}") from exc
        return None
    raise ValueError(f"Unsupported export format for {path.name}; expected CSV or XLSX.")


def _input(value: str) -> tuple[str, Path]:
    try:
        metadata_json, filename = value.split("=", 1)
        metadata = json.loads(metadata_json)
    except (ValueError, json.JSONDecodeError) as exc:
        raise argparse.ArgumentTypeError("--input must be JSON-metadata=local-export-path") from exc
    required = {"workbook", "spreadsheet_id", "tab_gid", "tab_name", "spreadsheet_revision", "role"}
    if not required.issubset(metadata) or not all(isinstance(metadata[key], str) for key in required):
        raise argparse.ArgumentTypeError(f"--input metadata requires string fields: {', '.join(sorted(required))}")
    if metadata["workbook"] not in REQUIRED_WORKBOOKS:
        raise argparse.ArgumentTypeError(f"--input workbook must be one of: {', '.join(sorted(REQUIRED_WORKBOOKS))}")
    if filename.startswith(("http://", "https://", "docs.google.com/", "drive.google.com/")):
        raise argparse.ArgumentTypeError("--input must name a staged local CSV or XLSX export, never a live Google URL")
    source = Path(filename).expanduser().resolve()
    if not source.is_file():
        raise argparse.ArgumentTypeError("--input source must be an existing CSV or XLSX export")
    try:
        _validate_file(source)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return json.dumps(metadata, sort_keys=True), source


def freeze(*, output_root: Path, batch_id: str, exported_at: str, inputs: list[tuple[str, Path]]) -> dict:
    target = output_root / batch_id
    if target.exists():
        raise FileExistsError(f"Snapshot batch already exists: {target}")
    metadata_inputs = [(json.loads(metadata_json), source) for metadata_json, source in inputs]
    identities = [(metadata["workbook"], metadata["tab_gid"]) for metadata, _ in metadata_inputs]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate workbook/tab identity in snapshot batch.")
    present_workbooks = {metadata["workbook"] for metadata, _ in metadata_inputs}
    missing_workbooks = sorted(REQUIRED_WORKBOOKS - present_workbooks)
    if missing_workbooks:
        raise ValueError(f"Incomplete six-workbook batch; missing: {', '.join(missing_workbooks)}")
    # Validate every input before creating even a temporary manifest directory.
    validated = [(metadata, source, _validate_file(source)) for metadata, source in metadata_inputs]
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{batch_id}-", dir=output_root))
    snapshots = []
    try:
        for metadata, source, row_count in validated:
            filename = f"{metadata['workbook']}-{metadata['tab_gid']}{source.suffix.lower()}"
            destination = temporary / filename
            shutil.copyfile(source, destination)
            snapshots.append({
                **metadata,
                "snapshot_file": filename,
                "exported_at_utc": exported_at,
                "sha256": _sha256(destination),
                "row_count": row_count,
                "importer_version": PARSER_VERSION,
            })
        snapshots.sort(key=lambda item: (item["workbook"], item["tab_gid"]))
        manifest = {
            "schema_version": 1,
            "season": 2026,
            "export_batch_id": batch_id,
            "exported_at_utc": exported_at,
            "importer_version": PARSER_VERSION,
            "snapshots": snapshots,
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--exported-at", required=True, help="UTC ISO-8601 timestamp captured when the local exports were downloaded.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--input", action="append", type=_input, required=True)
    args = parser.parse_args()
    manifest = freeze(output_root=args.output_root.resolve(), batch_id=args.batch_id, exported_at=args.exported_at, inputs=args.input)
    print(json.dumps({"export_batch_id": manifest["export_batch_id"], "snapshot_count": len(manifest["snapshots"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
