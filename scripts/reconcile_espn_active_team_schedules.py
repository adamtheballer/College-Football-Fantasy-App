#!/usr/bin/env python3
"""Strict, dry-run-first repair of active-roster TeamSchedule authority.

It never guesses a game from a team or week alone.  A schedule row may be
rewired only when the cached, previously verified ESPN event proves the exact
team/opponent pair for the same season and week.  Legacy Game rows are kept;
the stable TeamSchedule row is linked to the canonical ESPN Game row instead.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school
from collegefootballfantasy_api.app.services.provider_identity import audit_identity_event


VERSION = "espn-active-team-schedule-reconciliation-v1"


def key(value: str | None) -> str:
    return canonical_school_name(value or "") or normalize_school(value or "") or ""


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class CanonicalEvent:
    event_id: str
    season: int
    week: int
    home_team: str
    away_team: str
    kickoff: str
    status: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class PlannedRepair:
    category: str
    schedule_id: int
    team: str
    opponent: str | None
    old_event_id: str | None
    new_event_id: str | None
    old_kickoff: str | None
    new_kickoff: str | None
    canonical_game_action: str | None
    evidence: dict[str, Any]


def load_events(path: Path, *, season: int, week: int) -> list[CanonicalEvent]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", []) if isinstance(payload, dict) else payload
    result: list[CanonicalEvent] = []
    for record in records:
        if not isinstance(record, dict) or int(record.get("season") or 0) != season or int(record.get("week") or 0) != week:
            continue
        if not str(record.get("espn_event_id") or "").isdigit() or not key(record.get("home_team")) or not key(record.get("away_team")):
            continue
        result.append(CanonicalEvent(
            event_id=str(record["espn_event_id"]), season=season, week=week,
            home_team=str(record["home_team"]), away_team=str(record["away_team"]),
            kickoff=str(record.get("kickoff") or ""), status=str(record.get("status") or "pre"),
            evidence=dict(record.get("evidence") or {}),
        ))
    return result


def active_schedule_rows(db: Session, *, season: int, week: int) -> list[TeamSchedule]:
    active_schools = {
        key(school)
        for (school,) in (
            db.query(Player.school)
            .join(RosterEntry, RosterEntry.player_id == Player.id)
            .join(League, League.id == RosterEntry.league_id)
            .filter(RosterEntry.status == "active", League.season_year == season, League.status.notin_(("cancelled", "archived")))
            .distinct()
            .all()
        )
        if key(school)
    }
    return [row for row in db.query(TeamSchedule).filter(TeamSchedule.season == season, TeamSchedule.week == week).all() if key(row.team_name) in active_schools]


def plan_repairs(db: Session, *, season: int, week: int, events: list[CanonicalEvent]) -> list[PlannedRepair]:
    by_team: dict[str, list[CanonicalEvent]] = {}
    for event in events:
        by_team.setdefault(key(event.home_team), []).append(event)
        by_team.setdefault(key(event.away_team), []).append(event)
    plans: list[PlannedRepair] = []
    for row in active_schedule_rows(db, season=season, week=week):
        old_game = db.get(Game, row.game_id) if row.game_id else None
        old_event = old_game.external_id if old_game else None
        candidates = [event for event in by_team.get(key(row.team_name), []) if key(row.opponent_name) in {key(event.home_team), key(event.away_team)}]
        base = dict(schedule_id=row.id, team=row.team_name, opponent=row.opponent_name, old_event_id=old_event, old_kickoff=row.kickoff_at.isoformat() if row.kickoff_at else None)
        if not candidates:
            plans.append(PlannedRepair("NO_VERIFIED_EVENT", **base, new_event_id=None, new_kickoff=None, canonical_game_action=None, evidence={}))
            continue
        if len(candidates) != 1:
            plans.append(PlannedRepair("AMBIGUOUS", **base, new_event_id=None, new_kickoff=None, canonical_game_action=None, evidence={"candidate_event_ids": [event.event_id for event in candidates]}))
            continue
        event = candidates[0]
        participants = {key(event.home_team), key(event.away_team)}
        if {key(row.team_name), key(row.opponent_name)} != participants:
            plans.append(PlannedRepair("PARTICIPANT_CONFLICT", **base, new_event_id=event.event_id, new_kickoff=event.kickoff, canonical_game_action=None, evidence={"home_team": event.home_team, "away_team": event.away_team, **event.evidence}))
            continue
        canonical_games = db.query(Game).filter(Game.external_id == event.event_id).all()
        if len(canonical_games) > 1:
            plans.append(PlannedRepair("AMBIGUOUS", **base, new_event_id=event.event_id, new_kickoff=event.kickoff, canonical_game_action=None, evidence={"reason": "duplicate_canonical_event_id", "game_ids": [game.id for game in canonical_games], **event.evidence}))
            continue
        canonical_game = canonical_games[0] if canonical_games else None
        kickoff = datetime.fromisoformat(event.kickoff.replace("Z", "+00"))
        event_evidence = {"home_team": event.home_team, "away_team": event.away_team, "status": event.status, "version": VERSION, **event.evidence}
        if canonical_game is not None and (
            canonical_game.season != season
            or canonical_game.week != week
            or {key(canonical_game.home_team), key(canonical_game.away_team)} != participants
        ):
            plans.append(PlannedRepair("PARTICIPANT_CONFLICT", **base, new_event_id=event.event_id, new_kickoff=event.kickoff, canonical_game_action=None, evidence={"canonical_game_id": canonical_game.id, **event_evidence}))
            continue
        if canonical_game is not None and canonical_game.start_date is not None and as_utc(canonical_game.start_date) != as_utc(kickoff):
            plans.append(PlannedRepair("KICKOFF_CONFLICT", **base, new_event_id=event.event_id, new_kickoff=event.kickoff, canonical_game_action=None, evidence={"canonical_game_id": canonical_game.id, "canonical_kickoff": canonical_game.start_date.isoformat(), **event_evidence}))
            continue
        same_id = canonical_game is not None and row.game_id == canonical_game.id
        same_kickoff = row.kickoff_at is not None and as_utc(row.kickoff_at) == as_utc(kickoff)
        category = "HARMLESS_ALIAS_NORMALIZATION" if same_id and same_kickoff else "SAFE_KICKOFF_REPAIR" if same_id else "SAFE_ID_PROMOTION" if same_kickoff else "SAFE_ID_AND_KICKOFF_REPAIR"
        plans.append(PlannedRepair(category, **base, new_event_id=event.event_id, new_kickoff=event.kickoff, canonical_game_action="CREATE" if canonical_game is None else "REUSE", evidence={"canonical_game_id": canonical_game.id if canonical_game else None, **event_evidence}))
    return plans


def apply_repairs(db: Session, plans: list[PlannedRepair]) -> int:
    safe = {"SAFE_ID_PROMOTION", "SAFE_KICKOFF_REPAIR", "SAFE_ID_AND_KICKOFF_REPAIR"}
    if any(plan.category not in safe | {"HARMLESS_ALIAS_NORMALIZATION"} for plan in plans):
        raise RuntimeError("refusing apply: dry run contains non-safe schedule rows")
    writes = 0
    for plan in plans:
        if plan.category not in safe:
            continue
        row = db.get(TeamSchedule, plan.schedule_id)
        games = db.query(Game).filter(Game.external_id == plan.new_event_id).all()
        if len(games) > 1:
            raise RuntimeError(f"refusing apply: duplicate canonical event {plan.new_event_id}")
        kickoff = datetime.fromisoformat(str(plan.new_kickoff).replace("Z", "+00:00"))
        if not games:
            game = Game(
                external_id=plan.new_event_id,
                season=row.season,
                week=row.week,
                home_team=str(plan.evidence["home_team"]),
                away_team=str(plan.evidence["away_team"]),
                start_date=kickoff,
                schedule_status=str(plan.evidence.get("status") or "pre"),
            )
            db.add(game)
            db.flush()
            audit_identity_event(
                db,
                entity_type="game",
                entity_id=game.id,
                action="materialize_verified_espn_event",
                provider="espn",
                before_state=None,
                after_state={"event_id": game.external_id, "home_team": game.home_team, "away_team": game.away_team, "kickoff": kickoff.isoformat(), "evidence": plan.evidence},
                reason="Exact ESPN event participants and kickoff verified before active-roster schedule reconciliation.",
            )
        else:
            game = games[0]
            expected = {key(str(plan.evidence["home_team"])), key(str(plan.evidence["away_team"]))}
            if game.season != row.season or game.week != row.week or {key(game.home_team), key(game.away_team)} != expected or (game.start_date is not None and as_utc(game.start_date) != as_utc(kickoff)):
                raise RuntimeError(f"refusing apply: canonical event {plan.new_event_id} changed after dry run")
        before = {"game_id": row.game_id, "event_id": plan.old_event_id, "kickoff": plan.old_kickoff, "opponent": row.opponent_name}
        row.game_id, row.kickoff_at, row.game_date = game.id, kickoff, kickoff.date()
        row.opponent_name = game.away_team if key(row.team_name) == key(game.home_team) else game.home_team
        row.location = "home" if key(row.team_name) == key(game.home_team) else "away"
        row.is_bye, row.date_confirmed, row.source_url = False, True, "https://site.api.espn.com/"
        audit_identity_event(db, entity_type="team_schedule", entity_id=row.id, action="attach_verified_espn_event", provider="espn", before_state=before, after_state={"game_id": game.id, "event_id": game.external_id, "kickoff": kickoff.isoformat(), "evidence": plan.evidence}, reason="Exact cached ESPN event participants and kickoff verified before active-roster schedule reconciliation.")
        writes += 1
    db.flush()
    return writes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        plans = plan_repairs(db, season=args.season, week=args.week, events=load_events(args.events, season=args.season, week=args.week))
        counts = {category: sum(plan.category == category for plan in plans) for category in sorted({plan.category for plan in plans})}
        writes = apply_repairs(db, plans) if args.apply else 0
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps({"applied": args.apply, "writes": writes, "counts": counts, "plans": [asdict(plan) for plan in plans]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
