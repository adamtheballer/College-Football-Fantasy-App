from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "import_espn_historical_stats.py"


def load_module():
    spec = importlib.util.spec_from_file_location("import_espn_historical_stats", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_importer_resolves_unmapped_player_before_historical_import(monkeypatch):
    module = load_module()
    player = SimpleNamespace(id=7, name="Jeremiah Smith")
    lookup_calls: list[int] = []

    monkeypatch.setattr(module, "resolve_espn_player_id", lambda _db, _player: None)
    monkeypatch.setattr(module, "ESPNClient", lambda: object())
    monkeypatch.setattr(
        module,
        "resolve_espn_player_identity_and_profile",
        lambda _db, resolved_player, client: lookup_calls.append(resolved_player.id)
        or SimpleNamespace(
            outcome="matched",
            resolved=SimpleNamespace(provider_player_id="123"),
            profile_updated=True,
            detail=None,
        ),
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module.resolve_players_for_import(object(), [player], resolve_missing=True, dry_run=False)

    assert result.mapped_players == [player]
    assert result.already_mapped == 0
    assert result.newly_mapped == 1
    assert result.profile_rows_updated == 1
    assert result.unmatched == 0
    assert result.failed == 0
    assert lookup_calls == [7]


def test_importer_skips_identity_lookup_for_existing_trusted_mapping(monkeypatch):
    module = load_module()
    player = SimpleNamespace(id=8, name="Ahmad Hardy")
    db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)

    monkeypatch.setattr(module, "resolve_espn_player_id", lambda _db, _player: "456")
    monkeypatch.setattr(module, "ESPNClient", lambda: SimpleNamespace(get_athlete_profile=lambda _id: {"athlete": {}}))
    monkeypatch.setattr(module, "persist_espn_player_profile", lambda _player, _payload: True)
    monkeypatch.setattr(
        module,
        "resolve_espn_player_identity_and_profile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("existing mapping should be reused")),
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module.resolve_players_for_import(db, [player], resolve_missing=True, dry_run=False)

    assert result.mapped_players == [player]
    assert result.already_mapped == 1
    assert result.newly_mapped == 0
    assert result.profile_rows_updated == 1
    assert result.unmatched == 0


def test_dry_run_reports_unmapped_players_without_calling_espn(monkeypatch):
    module = load_module()
    player = SimpleNamespace(id=9, name="Dante Moore")

    monkeypatch.setattr(module, "resolve_espn_player_id", lambda _db, _player: None)
    monkeypatch.setattr(module, "ESPNClient", lambda: (_ for _ in ()).throw(AssertionError("dry run must not create a client")))
    monkeypatch.setattr(
        module,
        "resolve_espn_player_identity_and_profile",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dry run must not call ESPN")),
    )

    result = module.resolve_players_for_import(object(), [player], resolve_missing=True, dry_run=True)

    assert result.mapped_players == []
    assert result.already_mapped == 0
    assert result.newly_mapped == 0
    assert result.unmatched == 1


def test_importer_records_ambiguous_identity_for_follow_up(monkeypatch):
    module = load_module()
    player = SimpleNamespace(id=10, name="Duplicate Name")
    recorded: list[tuple[str, str | None]] = []

    monkeypatch.setattr(module, "resolve_espn_player_id", lambda _db, _player: None)
    monkeypatch.setattr(module, "ESPNClient", lambda: object())
    monkeypatch.setattr(
        module,
        "resolve_espn_player_identity_and_profile",
        lambda *_args, **_kwargs: SimpleNamespace(
            outcome="ambiguous", resolved=None, profile_updated=False, detail="multiple exact matches"
        ),
    )
    monkeypatch.setattr(
        module,
        "record_identity_outcome",
        lambda _db, _player, outcome, detail: recorded.append((outcome, detail)),
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module.resolve_players_for_import(object(), [player], resolve_missing=True, dry_run=False)

    assert result.mapped_players == []
    assert result.ambiguous == 1
    assert result.not_found == 0
    assert recorded == [("ambiguous", "multiple exact matches")]
