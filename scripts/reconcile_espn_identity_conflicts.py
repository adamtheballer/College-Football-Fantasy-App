"""Transactionally replace explicitly reviewed stale ESPN player identities.

This tool deliberately has no discovery or fuzzy-match path.  It accepts only
an operator-reviewed decision file, validates every expected old mapping and
the unique target ownership first, then writes the replacements and a durable
identity audit trail in one transaction.  Without ``--apply`` it rolls back.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.provider_identity import (
    ProviderIdentityConflict,
    audit_identity_event,
)


SCRIPT_VERSION = "espn-identity-conflict-reconciliation-v1"


@dataclass(frozen=True)
class IdentityDecision:
    internal_player_id: int
    expected_provider_player_id: str
    replacement_provider_player_id: str
    replacement_provider_team_id: str
    evidence: dict[str, Any]


def _mapping_state(mapping: PlayerProviderId) -> dict[str, Any]:
    return {
        "player_id": mapping.player_id,
        "provider_player_id": mapping.provider_player_id,
        "provider_team_id": mapping.provider_team_id,
        "match_confidence": mapping.match_confidence,
        "verification_status": mapping.verification_status,
        "verified_at": mapping.verified_at.isoformat() if mapping.verified_at else None,
        "verified_by_user_id": mapping.verified_by_user_id,
    }


def load_decisions(path: Path) -> list[IdentityDecision]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("decision file must contain a non-empty JSON list")
    decisions: list[IdentityDecision] = []
    for item in payload:
        required = {
            "internal_player_id",
            "expected_provider_player_id",
            "replacement_provider_player_id",
            "replacement_provider_team_id",
            "evidence",
        }
        missing = required.difference(item)
        if missing:
            raise ValueError(f"decision missing required keys: {', '.join(sorted(missing))}")
        if not isinstance(item["evidence"], dict):
            raise ValueError("decision evidence must be an object")
        decisions.append(
            IdentityDecision(
                internal_player_id=int(item["internal_player_id"]),
                expected_provider_player_id=str(item["expected_provider_player_id"]),
                replacement_provider_player_id=str(item["replacement_provider_player_id"]),
                replacement_provider_team_id=str(item["replacement_provider_team_id"]),
                evidence=item["evidence"],
            )
        )
    if len({decision.internal_player_id for decision in decisions}) != len(decisions):
        raise ValueError("a player may have only one conflict decision")
    if len({decision.replacement_provider_player_id for decision in decisions}) != len(decisions):
        raise ValueError("a replacement ESPN athlete ID may appear only once")
    return decisions


def _validate_decisions(db: Session, decisions: list[IdentityDecision]) -> dict[int, PlayerProviderId]:
    mappings: dict[int, PlayerProviderId] = {}
    for decision in decisions:
        mapping = db.scalar(
            select(PlayerProviderId).where(
                PlayerProviderId.player_id == decision.internal_player_id,
                PlayerProviderId.provider == "espn",
            )
        )
        if mapping is None:
            raise ProviderIdentityConflict(f"missing ESPN mapping for player {decision.internal_player_id}")
        if mapping.provider_player_id != decision.expected_provider_player_id:
            raise ProviderIdentityConflict(
                f"player {decision.internal_player_id} expected {decision.expected_provider_player_id}, "
                f"found {mapping.provider_player_id}"
            )
        target_owner = db.scalar(
            select(PlayerProviderId).where(
                PlayerProviderId.provider == "espn",
                PlayerProviderId.provider_player_id == decision.replacement_provider_player_id,
            )
        )
        if target_owner is not None and target_owner.id != mapping.id:
            raise ProviderIdentityConflict(
                f"replacement ESPN athlete ID {decision.replacement_provider_player_id} is already owned by "
                f"player {target_owner.player_id}"
            )
        mappings[decision.internal_player_id] = mapping
    return mappings


def reconcile_decisions(db: Session, decisions: list[IdentityDecision]) -> int:
    """Validate all decisions before changing any one mapping, then audit each replacement."""

    mappings = _validate_decisions(db, decisions)
    reconciled_at = datetime.now(timezone.utc)
    for decision in decisions:
        mapping = mappings[decision.internal_player_id]
        before_state = _mapping_state(mapping)
        mapping.provider_player_id = decision.replacement_provider_player_id
        mapping.provider_team_id = decision.replacement_provider_team_id
        mapping.match_confidence = 1.0
        mapping.verification_status = "verified"
        mapping.verified_at = reconciled_at
        mapping.verified_by_user_id = None
        after_state = {
            **_mapping_state(mapping),
            "operator": "approved_forensic_reconciliation",
            "script_version": SCRIPT_VERSION,
            "evidence": decision.evidence,
        }
        audit_identity_event(
            db,
            entity_type="player_provider_id",
            entity_id=mapping.id,
            action="replace_verified_mapping",
            provider="espn",
            provider_player_id=mapping.provider_player_id,
            provider_team_id=mapping.provider_team_id,
            before_state=before_state,
            after_state=after_state,
            reason="Approved exact current ESPN roster/profile identity reconciliation; prior workbook mapping retained in audit history.",
        )
    db.flush()
    return len(decisions)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True, help="Reviewed JSON conflict-decision file.")
    parser.add_argument("--apply", action="store_true", help="Commit the validated replacements. Without this flag, roll back.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    decisions = load_decisions(args.decisions)
    ensure_models_registered()
    with SessionLocal() as db:
        reconciled = reconcile_decisions(db, decisions)
        result = {"decisions": len(decisions), "reconciled": reconciled, "applied": args.apply}
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
