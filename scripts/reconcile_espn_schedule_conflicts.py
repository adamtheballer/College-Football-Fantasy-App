"""Transactionally reconcile an explicitly reviewed stale ESPN schedule row.

No schedule is discovered or matched here.  Each decision must state the exact
legacy game external ID that is expected in production; otherwise the tool
refuses to write.  The existing Game row is updated in place so foreign-key
history is preserved, and ProviderIdentityAudit records the complete evidence.
Without ``--apply`` this command always rolls back.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.provider_identity import ProviderIdentityConflict, audit_identity_event


SCRIPT_VERSION = "espn-schedule-conflict-reconciliation-v1"
ESPN_SOURCE_URL = "https://site.api.espn.com/"


@dataclass(frozen=True)
class ScheduleDecision:
    team_name: str
    season: int
    week: int
    expected_game_external_id: str
    replacement_event_id: str
    home_team: str
    away_team: str
    kickoff: str
    status: str
    evidence: dict[str, Any]


def _schedule_state(row: TeamSchedule, game: Game) -> dict[str, Any]:
    return {
        "schedule": {
            "id": row.id,
            "team_name": row.team_name,
            "season": row.season,
            "week": row.week,
            "game_id": row.game_id,
            "opponent_name": row.opponent_name,
            "location": row.location,
            "is_bye": row.is_bye,
            "game_date": row.game_date.isoformat() if row.game_date else None,
            "kickoff_at": row.kickoff_at.isoformat() if row.kickoff_at else None,
            "date_confirmed": row.date_confirmed,
            "source_url": row.source_url,
        },
        "game": {
            "id": game.id,
            "external_id": game.external_id,
            "home_team": game.home_team,
            "away_team": game.away_team,
            "start_date": game.start_date.isoformat() if game.start_date else None,
            "schedule_status": game.schedule_status,
        },
    }


def load_decisions(path: Path) -> list[ScheduleDecision]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("decision file must contain a non-empty JSON list")
    required = {
        "team_name", "season", "week", "expected_game_external_id", "replacement_event_id",
        "home_team", "away_team", "kickoff", "status", "evidence",
    }
    decisions: list[ScheduleDecision] = []
    for item in payload:
        missing = required.difference(item)
        if missing:
            raise ValueError(f"decision missing required keys: {', '.join(sorted(missing))}")
        if not isinstance(item["evidence"], dict):
            raise ValueError("decision evidence must be an object")
        decisions.append(
            ScheduleDecision(
                team_name=str(item["team_name"]), season=int(item["season"]), week=int(item["week"]),
                expected_game_external_id=str(item["expected_game_external_id"]),
                replacement_event_id=str(item["replacement_event_id"]), home_team=str(item["home_team"]),
                away_team=str(item["away_team"]), kickoff=str(item["kickoff"]), status=str(item["status"]),
                evidence=item["evidence"],
            )
        )
    if len({(d.team_name, d.season, d.week) for d in decisions}) != len(decisions):
        raise ValueError("a team/week may have only one schedule decision")
    if len({d.replacement_event_id for d in decisions}) != len(decisions):
        raise ValueError("a replacement ESPN event ID may appear only once")
    return decisions


def _validated_rows(db: Session, decisions: list[ScheduleDecision]) -> list[tuple[ScheduleDecision, TeamSchedule, Game]]:
    result: list[tuple[ScheduleDecision, TeamSchedule, Game]] = []
    for decision in decisions:
        row = db.scalar(select(TeamSchedule).where(
            TeamSchedule.team_name == decision.team_name,
            TeamSchedule.season == decision.season,
            TeamSchedule.week == decision.week,
        ))
        if row is None or row.game_id is None:
            raise ProviderIdentityConflict(f"missing linked schedule row for {decision.team_name} week {decision.week}")
        game = db.get(Game, row.game_id)
        if game is None or game.external_id != decision.expected_game_external_id:
            raise ProviderIdentityConflict(f"unexpected legacy game for {decision.team_name} week {decision.week}")
        owner = db.scalar(select(Game).where(Game.external_id == decision.replacement_event_id))
        if owner is not None and owner.id != game.id:
            raise ProviderIdentityConflict(f"replacement ESPN event {decision.replacement_event_id} already belongs to game {owner.id}")
        result.append((decision, row, game))
    return result


def reconcile_decisions(db: Session, decisions: list[ScheduleDecision]) -> int:
    """Validate every old row before changing any one schedule or game."""

    rows = _validated_rows(db, decisions)
    for decision, row, game in rows:
        before_state = _schedule_state(row, game)
        kickoff = datetime.fromisoformat(decision.kickoff)
        if row.team_name == decision.home_team:
            opponent_name, location = decision.away_team, "home"
        elif row.team_name == decision.away_team:
            opponent_name, location = decision.home_team, "away"
        else:
            raise ProviderIdentityConflict(f"reviewed team is not a participant in event {decision.replacement_event_id}")
        game.external_id = decision.replacement_event_id
        game.home_team = decision.home_team
        game.away_team = decision.away_team
        game.start_date = kickoff
        game.schedule_status = decision.status
        row.opponent_name = opponent_name
        row.location = location
        row.is_bye = False
        row.game_date = kickoff.date()
        row.kickoff_at = kickoff
        row.date_confirmed = True
        row.source_url = ESPN_SOURCE_URL
        after_state = {
            **_schedule_state(row, game),
            "operator": "approved_forensic_reconciliation",
            "script_version": SCRIPT_VERSION,
            "evidence": decision.evidence,
        }
        audit_identity_event(
            db,
            entity_type="team_schedule",
            entity_id=row.id,
            action="replace_verified_schedule",
            provider="espn",
            provider_team_id=None,
            before_state=before_state,
            after_state=after_state,
            reason="Approved current ESPN schedule reconciliation; legacy spreadsheet state retained in audit history.",
        )
    db.flush()
    return len(decisions)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Commit validated schedule replacements; otherwise roll back.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    decisions = load_decisions(args.decisions)
    ensure_models_registered()
    with SessionLocal() as db:
        reconciled = reconcile_decisions(db, decisions)
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps({"applied": args.apply, "decisions": len(decisions), "reconciled": reconciled}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
