import json

import pytest

from scripts.freeze_authoritative_sheet_snapshots import _input, freeze


def test_freeze_copies_exact_export_bytes_and_records_reproducible_provenance(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("name,value\nKewan Lacy,291.2\n", encoding="utf-8")
    metadata = json.dumps({
        "workbook": "annual_projections",
        "spreadsheet_id": "sheet-id",
        "tab_gid": "123",
        "tab_name": "SEC",
        "spreadsheet_revision": "923",
        "role": "annual_component_projections",
    }, sort_keys=True)

    inputs = []
    for index, workbook in enumerate(sorted({"player_id_details", "team_rankings", "player_previous_stats", "annual_projections", "schedules", "cfb27_ratings"})):
        item = json.loads(metadata)
        item["workbook"] = workbook
        item["tab_gid"] = str(index)
        inputs.append((json.dumps(item, sort_keys=True), source))
    manifest = freeze(output_root=tmp_path / "sealed", batch_id="batch-a", exported_at="2026-08-09T00:00:00Z", inputs=inputs)

    entry = manifest["snapshots"][0]
    assert entry["row_count"] == 2
    assert entry["spreadsheet_revision"] == "923"
    snapshot = tmp_path / "sealed" / "batch-a" / entry["snapshot_file"]
    assert snapshot.read_bytes() == source.read_bytes()
    assert json.loads((snapshot.parent / "manifest.json").read_text()) == manifest


def test_freeze_rejects_incomplete_duplicate_and_malformed_batches_without_manifest(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("name\nKewan Lacy\n", encoding="utf-8")
    metadata = {"workbook": "annual_projections", "spreadsheet_id": "id", "tab_gid": "0", "tab_name": "SEC", "spreadsheet_revision": "923", "role": "annual"}
    with pytest.raises(ValueError, match="Incomplete"):
        freeze(output_root=tmp_path / "sealed", batch_id="missing", exported_at="2026-08-09T00:00:00Z", inputs=[(json.dumps(metadata), source)])
    assert not (tmp_path / "sealed" / "missing").exists()

    all_inputs = []
    for index, workbook in enumerate(sorted({"player_id_details", "team_rankings", "player_previous_stats", "annual_projections", "schedules", "cfb27_ratings"})):
        item = {**metadata, "workbook": workbook, "tab_gid": str(index)}
        all_inputs.append((json.dumps(item), source))
    all_inputs.append(all_inputs[0])
    with pytest.raises(ValueError, match="Duplicate"):
        freeze(output_root=tmp_path / "sealed", batch_id="duplicate", exported_at="2026-08-09T00:00:00Z", inputs=all_inputs)
    assert not (tmp_path / "sealed" / "duplicate").exists()


def test_snapshot_input_rejects_live_urls_and_malformed_exports(tmp_path):
    metadata = {"workbook": "annual_projections", "spreadsheet_id": "id", "tab_gid": "0", "tab_name": "SEC", "spreadsheet_revision": "923", "role": "annual"}
    with pytest.raises(Exception, match="live Google URL"):
        _input(f'{json.dumps(metadata)}=https://docs.google.com/spreadsheets/d/id')
    with pytest.raises(Exception, match="live Google URL"):
        _input(f'{json.dumps(metadata)}=http://example.test/export.csv')
    invalid = tmp_path / "invalid.xlsx"
    invalid.write_text("not an xlsx", encoding="utf-8")
    with pytest.raises(Exception, match="Malformed XLSX"):
        _input(f"{json.dumps(metadata)}={invalid}")


def test_changed_source_bytes_change_the_sealed_snapshot_hash(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("name\nKewan Lacy\n", encoding="utf-8")
    def inputs_for(path):
        return [
            (json.dumps({"workbook": workbook, "spreadsheet_id": "id", "tab_gid": str(index), "tab_name": "tab", "spreadsheet_revision": "1", "role": workbook}), path)
            for index, workbook in enumerate(sorted({"player_id_details", "team_rankings", "player_previous_stats", "annual_projections", "schedules", "cfb27_ratings"}))
        ]
    first = freeze(output_root=tmp_path / "sealed", batch_id="first", exported_at="2026-08-09T00:00:00Z", inputs=inputs_for(source))
    source.write_text("name\nKewan Lacy\nChanged\n", encoding="utf-8")
    second = freeze(output_root=tmp_path / "sealed", batch_id="second", exported_at="2026-08-09T00:00:00Z", inputs=inputs_for(source))
    assert first["snapshots"][0]["sha256"] != second["snapshots"][0]["sha256"]
