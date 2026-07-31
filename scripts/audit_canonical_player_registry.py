#!/usr/bin/env python3
"""Verify the reviewed source snapshot resolves to the application's player registry.

The human-maintained identity workbook deliberately does not contain an
application primary key.  ``players.id`` is the canonical internal identifier
created and maintained by the application.  This audit proves that every row
in an approved, immutable identity/projection snapshot resolves to exactly one
such player before a release can be promoted.

This command is read-only: it never mutates the database, Google Sheets, or
the source snapshots.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.player import Player
from scripts.audit_preseason_source_contract import (
    DEFAULT_SOURCE_DIRECTORY,
    PreseasonSourceContractError,
    require_valid_contract,
    require_valid_source_directory,
)
from scripts.bootstrap_canonical_player_data import identity_key, read_rows


SOURCE_PREFIX = "canonical-preseason:2026:"


def _display(key: tuple[str, str, str]) -> str:
    name, school, position = key
    return f"{name or '<blank>'} | {school or '<blank>'} | {position or '<blank>'}"


def _source_keys(
    identity_rows: list[dict[str, str]], projection_rows: list[dict[str, str]]
) -> set[tuple[str, str, str]]:
    """Return exact source keys only after the two reviewed exports agree."""

    require_valid_contract(projection_rows, identity_rows)
    return {
        identity_key(row.get("NAME"), row.get("SCHOOL"), row.get("POSITION"))
        for row in identity_rows
    }


def audit_canonical_player_registry(
    *,
    identity_rows: list[dict[str, str]],
    projection_rows: list[dict[str, str]],
    players: Iterable[Player],
) -> dict[str, Any]:
    """Compare the approved snapshot to the app-owned canonical registry.

    A source row is identified by the exact normalized ``name + school +
    position`` key already used by the idempotent bootstrap.  The canonical
    identifier is deliberately the database primary key, not a column the
    source spreadsheet must duplicate.
    """

    source_keys = _source_keys(identity_rows, projection_rows)
    registry: dict[tuple[str, str, str], list[Player]] = defaultdict(list)
    bootstrap_players: list[Player] = []
    invalid_registry_player_ids: list[str] = []

    for player in players:
        key = identity_key(player.name, player.school, player.position)
        registry[key].append(player)
        if getattr(player, "id", None) is None:
            invalid_registry_player_ids.append(_display(key))
        source_marker = getattr(player, "sheet_source_sheet_id", None) or ""
        if source_marker.startswith(SOURCE_PREFIX):
            bootstrap_players.append(player)

    missing_source_keys = sorted(key for key in source_keys if not registry.get(key))
    ambiguous_source_keys = sorted(key for key in source_keys if len(registry.get(key, [])) > 1)
    unmapped_bootstrap_players = sorted(
        _display(identity_key(player.name, player.school, player.position))
        for player in bootstrap_players
        if identity_key(player.name, player.school, player.position) not in source_keys
    )
    mapped_player_ids = {
        player.id
        for key in source_keys
        for player in registry.get(key, [])
        if getattr(player, "id", None) is not None
    }

    has_errors = bool(
        missing_source_keys
        or ambiguous_source_keys
        or invalid_registry_player_ids
        or unmapped_bootstrap_players
    )
    return {
        "status": "FAIL" if has_errors else "PASS",
        "canonical_id_owner": "application database players.id",
        "source_canonical_id_column_required": False,
        "source_player_count": len(source_keys),
        "mapped_internal_player_count": len(mapped_player_ids),
        "source_keys_without_internal_player_count": len(missing_source_keys),
        "source_keys_without_internal_player": [_display(key) for key in missing_source_keys],
        "source_keys_with_multiple_internal_players_count": len(ambiguous_source_keys),
        "source_keys_with_multiple_internal_players": [
            {
                "source_key": _display(key),
                "player_ids": sorted(player.id for player in registry[key] if player.id is not None),
            }
            for key in ambiguous_source_keys
        ],
        "internal_players_without_primary_key_count": len(invalid_registry_player_ids),
        "internal_players_without_primary_key": sorted(invalid_registry_player_ids),
        "bootstrap_players_absent_from_approved_snapshot_count": len(unmapped_bootstrap_players),
        "bootstrap_players_absent_from_approved_snapshot": unmapped_bootstrap_players,
        "note": (
            "The source workbook remains human-editable. Immutable source snapshots are "
            "reconciled to the app-owned players.id registry; provider mappings are audited "
            "separately because a source row need not have a provider identifier."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the reviewed player snapshot maps one-to-one to application canonical IDs."
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIRECTORY)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    try:
        require_valid_source_directory(source_dir)
    except PreseasonSourceContractError as error:
        print(f"canonical registry audit rejected: {error}")
        return 1

    identity_rows = read_rows(source_dir / "player-identities.csv")
    projection_rows = read_rows(source_dir / "player-projections.csv")
    ensure_models_registered()
    with SessionLocal() as db:
        report = audit_canonical_player_registry(
            identity_rows=identity_rows,
            projection_rows=projection_rows,
            players=db.scalars(select(Player)).all(),
        )

    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())



