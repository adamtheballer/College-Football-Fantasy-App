from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "backfill_espn_headshots.py"


def load_module():
    spec = importlib.util.spec_from_file_location("backfill_espn_headshots", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_reuses_verified_identity_and_only_persists_profile(monkeypatch):
    module = load_module()
    player = SimpleNamespace(id=7, name="Jeremiah Smith", image_url=None, espn_headshot_url=None)
    db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    calls: list[str] = []

    monkeypatch.setattr(module, "resolve_espn_player_id", lambda _db, _player: "123")
    monkeypatch.setattr(module, "persist_espn_player_profile", lambda resolved, _payload: setattr(resolved, "image_url", "https://espn.test/123.png") or True)
    client = SimpleNamespace(get_athlete_profile=lambda provider_id: calls.append(provider_id) or {"athlete": {"id": provider_id}})
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module.backfill_headshots(db, [player], client=client, dry_run=False, delay_seconds=0)

    assert calls == ["123"]
    assert result.updated == 1
    assert result.matched == 1
    assert result.unresolved == 0


def test_backfill_never_guesses_unmapped_headshot_url(monkeypatch):
    module = load_module()
    player = SimpleNamespace(id=8, name="Ambiguous Player", image_url=None, espn_headshot_url=None)
    db = SimpleNamespace(rollback=lambda: None)

    monkeypatch.setattr(module, "resolve_espn_player_id", lambda _db, _player: None)
    monkeypatch.setattr(
        module,
        "resolve_espn_player_identity_and_profile",
        lambda *_args, **_kwargs: SimpleNamespace(outcome="ambiguous"),
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)

    result = module.backfill_headshots(db, [player], client=object(), dry_run=False, delay_seconds=0)

    assert player.image_url is None
    assert result.updated == 0
    assert result.unresolved == 1
