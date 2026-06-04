from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.app.models.league_settings import LeagueSettings
from api.app.models.notification import NotificationLog
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.models.transaction import Transaction
from api.app.models.waiver_claim import WaiverClaim
from api.app.schemas.waiver import WaiverProcessResponse, WaiverProcessResultRow
from api.app.services.event_stream import append_league_event

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}
PENDING_STATUSES = {"pending"}


@dataclass
class WaiverProcessExecutionResult:
    response: WaiverProcessResponse


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _league_settings(db: Session, league_id: int) -> LeagueSettings:
    row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")
    return row


def _waiver_mode(settings_row: LeagueSettings) -> str:
    value = (settings_row.waiver_type or "priority").strip().lower()
    if value in {"faab", "faab waivers", "faab_waivers"}:
        return "faab"
    return "priority"


def _slot_limits(settings_row: LeagueSettings) -> dict[str, int]:
    slots = settings_row.roster_slots_json or DEFAULT_ROSTER_SLOTS
    if not isinstance(slots, dict):
        return DEFAULT_ROSTER_SLOTS
    return {str(k): int(v) for k, v in slots.items()}


def _team_rows_for_league(db: Session, league_id: int) -> list[Team]:
    return (
        db.query(Team)
        .filter(Team.league_id == league_id)
        .order_by(Team.created_at.asc(), Team.id.asc())
        .all()
    )


def _ensure_team_waiver_state(db: Session, league_id: int) -> list[Team]:
    teams = _team_rows_for_league(db, league_id)
    if not teams:
        return []

    next_priority = 1
    for team in teams:
        if team.waiver_priority and team.waiver_priority > 0:
            continue
        team.waiver_priority = next_priority
        next_priority += 1
        db.add(team)

    sorted_by_priority = sorted(teams, key=lambda row: (int(row.waiver_priority or 0), row.id))
    for index, team in enumerate(sorted_by_priority, start=1):
        if team.waiver_priority != index:
            team.waiver_priority = index
            db.add(team)
        if team.faab_balance is None or team.faab_balance < 0:
            team.faab_balance = 100
            db.add(team)

    return sorted(sorted_by_priority, key=lambda row: (int(row.waiver_priority or 0), row.id))


def _team_name_map(db: Session, league_id: int) -> dict[int, str]:
    return {
        row.id: row.name
        for row in db.query(Team.id, Team.name).filter(Team.league_id == league_id).all()
    }


def _player_map(db: Session, player_ids: set[int]) -> dict[int, Player]:
    if not player_ids:
        return {}
    rows = db.query(Player).filter(Player.id.in_(player_ids)).all()
    return {row.id: row for row in rows}


def _record_transaction(
    db: Session,
    *,
    league_id: int,
    team_id: int,
    transaction_type: str,
    created_by_user_id: int | None,
    player_id: int | None = None,
    related_player_id: int | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        Transaction(
            league_id=league_id,
            team_id=team_id,
            transaction_type=transaction_type,
            player_id=player_id,
            related_player_id=related_player_id,
            created_by_user_id=created_by_user_id,
            reason=reason,
        )
    )


def _roster_rows_for_league(db: Session, league_id: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league_id)
        .all()
    )


def _find_roster_entry(rows: list[RosterEntry], player_id: int) -> RosterEntry | None:
    for row in rows:
        if row.player_id == player_id:
            return row
    return None


def _resolve_best_slot(
    *,
    team_rows: list[RosterEntry],
    slot_limits: dict[str, int],
    player_position: str,
    drop_player_id: int | None,
) -> str | None:
    counts: dict[str, int] = {}
    for row in team_rows:
        if drop_player_id is not None and row.player_id == drop_player_id:
            continue
        counts[row.slot] = counts.get(row.slot, 0) + 1

    primary_limit = int(slot_limits.get(player_position, 0))
    if primary_limit > counts.get(player_position, 0):
        return player_position

    bench_limit = int(slot_limits.get("BENCH", 0))
    if bench_limit > counts.get("BENCH", 0):
        return "BENCH"

    return None


def _emit_waiver_event(db: Session, *, league_id: int, event_type: str, payload: dict) -> None:
    append_league_event(
        db,
        league_id=league_id,
        event_type=event_type,
        entity_type="waiver",
        payload=payload,
    )


def process_pending_waiver_claims(
    db: Session,
    *,
    league_id: int,
    acted_by_user_id: int | None,
    batch_key: str,
) -> WaiverProcessExecutionResult:
    settings_row = _league_settings(db, league_id)
    waiver_mode = _waiver_mode(settings_row)
    slot_limits = _slot_limits(settings_row)

    teams = _ensure_team_waiver_state(db, league_id)
    team_by_id = {row.id: row for row in teams}
    if not teams:
        return WaiverProcessExecutionResult(
            response=WaiverProcessResponse(
                batch_key=batch_key,
                processed_count=0,
                won_count=0,
                lost_count=0,
                invalid_count=0,
                data=[],
            )
        )

    pending_claims = (
        db.query(WaiverClaim)
        .filter(WaiverClaim.league_id == league_id, WaiverClaim.status.in_(list(PENDING_STATUSES)))
        .order_by(WaiverClaim.created_at.asc(), WaiverClaim.id.asc())
        .all()
    )
    if not pending_claims:
        return WaiverProcessExecutionResult(
            response=WaiverProcessResponse(
                batch_key=batch_key,
                processed_count=0,
                won_count=0,
                lost_count=0,
                invalid_count=0,
                data=[],
            )
        )

    claim_player_ids: set[int] = set()
    for claim in pending_claims:
        claim_player_ids.add(claim.add_player_id)
        if claim.drop_player_id is not None:
            claim_player_ids.add(claim.drop_player_id)

    player_by_id = _player_map(db, claim_player_ids)
    team_name_by_id = _team_name_map(db, league_id)

    roster_rows = _roster_rows_for_league(db, league_id)
    roster_by_team: dict[int, list[RosterEntry]] = defaultdict(list)
    roster_team_by_player: dict[int, int] = {}
    for row in roster_rows:
        roster_by_team[row.team_id].append(row)
        roster_team_by_player[row.player_id] = row.team_id

    grouped: dict[int, list[WaiverClaim]] = defaultdict(list)
    for claim in pending_claims:
        grouped[claim.add_player_id].append(claim)

    results: list[WaiverProcessResultRow] = []

    def _mark_claim(
        claim: WaiverClaim,
        *,
        status_value: str,
        reason: str | None,
    ) -> None:
        claim.status = status_value
        claim.processed_reason = reason
        claim.processed_at = _utc_now()
        claim.process_batch_key = batch_key
        db.add(claim)
        player = player_by_id.get(claim.add_player_id)
        results.append(
            WaiverProcessResultRow(
                claim_id=claim.id,
                team_id=claim.team_id,
                team_name=team_name_by_id.get(claim.team_id),
                add_player_id=claim.add_player_id,
                add_player_name=player.name if player else None,
                bid_amount=int(claim.bid_amount or 0),
                status=claim.status,
                reason=reason,
            )
        )

    def _normalize_waiver_priorities() -> None:
        ordered = sorted(team_by_id.values(), key=lambda row: (int(row.waiver_priority or 0), row.id))
        for index, row in enumerate(ordered, start=1):
            if row.waiver_priority != index:
                row.waiver_priority = index
                db.add(row)

    for add_player_id in sorted(grouped.keys()):
        claims = grouped[add_player_id]
        add_player = player_by_id.get(add_player_id)
        if not add_player:
            for claim in claims:
                _mark_claim(claim, status_value="invalid", reason="add player not found")
            continue

        available = add_player_id not in roster_team_by_player
        valid_claims: list[tuple[WaiverClaim, str]] = []

        for claim in claims:
            team = team_by_id.get(claim.team_id)
            if not team:
                _mark_claim(claim, status_value="invalid", reason="team not found")
                continue
            if not available:
                _mark_claim(claim, status_value="invalid", reason="player already rostered")
                continue

            team_rows = roster_by_team.get(team.id, [])
            if any(row.player_id == claim.add_player_id for row in team_rows):
                _mark_claim(claim, status_value="invalid", reason="player already on roster")
                continue
            if claim.drop_player_id is not None and _find_roster_entry(team_rows, claim.drop_player_id) is None:
                _mark_claim(claim, status_value="invalid", reason="drop player not on roster")
                continue

            slot = _resolve_best_slot(
                team_rows=team_rows,
                slot_limits=slot_limits,
                player_position=add_player.position,
                drop_player_id=claim.drop_player_id,
            )
            if slot is None:
                _mark_claim(claim, status_value="invalid", reason="roster full for claim")
                continue

            if waiver_mode == "faab" and int(claim.bid_amount or 0) > int(team.faab_balance or 0):
                _mark_claim(claim, status_value="invalid", reason="insufficient FAAB balance")
                continue

            valid_claims.append((claim, slot))

        if not valid_claims:
            continue

        def _sort_key(item: tuple[WaiverClaim, str]) -> tuple:
            claim, _slot = item
            team = team_by_id[claim.team_id]
            if waiver_mode == "faab":
                return (
                    -int(claim.bid_amount or 0),
                    int(team.waiver_priority or 0),
                    claim.created_at,
                    claim.id,
                )
            return (
                int(team.waiver_priority or 0),
                claim.created_at,
                claim.id,
            )

        valid_claims.sort(key=_sort_key)
        winner_claim, winner_slot = valid_claims[0]
        winner_team = team_by_id[winner_claim.team_id]

        winner_team_rows = roster_by_team.get(winner_team.id, [])
        dropped_player_id: int | None = None
        if winner_claim.drop_player_id is not None:
            drop_entry = _find_roster_entry(winner_team_rows, winner_claim.drop_player_id)
            if drop_entry is not None:
                dropped_player_id = drop_entry.player_id
                winner_team_rows.remove(drop_entry)
                db.delete(drop_entry)
                roster_team_by_player.pop(drop_entry.player_id, None)

        new_entry = RosterEntry(
            league_id=league_id,
            team_id=winner_team.id,
            player_id=winner_claim.add_player_id,
            slot=winner_slot,
            status="active",
        )
        db.add(new_entry)
        db.flush()

        winner_team_rows = roster_by_team.get(winner_team.id, [])
        winner_team_rows.append(new_entry)
        roster_by_team[winner_team.id] = winner_team_rows
        roster_team_by_player[winner_claim.add_player_id] = winner_team.id

        if waiver_mode == "faab":
            winner_team.faab_balance = max(0, int(winner_team.faab_balance or 0) - int(winner_claim.bid_amount or 0))
            db.add(winner_team)

        max_priority = max(int(row.waiver_priority or 0) for row in team_by_id.values())
        winner_team.waiver_priority = max_priority + 1
        db.add(winner_team)
        _normalize_waiver_priorities()

        _record_transaction(
            db,
            league_id=league_id,
            team_id=winner_team.id,
            transaction_type="waiver_add",
            created_by_user_id=acted_by_user_id,
            player_id=winner_claim.add_player_id,
            related_player_id=dropped_player_id,
            reason=f"{batch_key} awarded",
        )
        if dropped_player_id is not None:
            _record_transaction(
                db,
                league_id=league_id,
                team_id=winner_team.id,
                transaction_type="waiver_drop",
                created_by_user_id=acted_by_user_id,
                player_id=dropped_player_id,
                related_player_id=winner_claim.add_player_id,
                reason=f"{batch_key} awarded",
            )

        db.add(
            NotificationLog(
                user_id=winner_team.owner_user_id,
                user_key=f"user:{winner_team.owner_user_id}",
                alert_type="WAIVER",
                title="Waiver claim awarded",
                body=f"{winner_team.name} won {add_player.name}.",
                payload={
                    "league_id": league_id,
                    "claim_id": winner_claim.id,
                    "team_id": winner_team.id,
                    "player_id": winner_claim.add_player_id,
                    "batch_key": batch_key,
                },
            )
        )
        _mark_claim(winner_claim, status_value="won", reason="awarded")

        for losing_claim, _slot in valid_claims[1:]:
            if waiver_mode == "faab":
                winner_bid = int(winner_claim.bid_amount or 0)
                loser_bid = int(losing_claim.bid_amount or 0)
                if loser_bid < winner_bid:
                    reason = "outbid"
                else:
                    reason = "priority tiebreak"
            else:
                reason = "waiver priority"
            _mark_claim(losing_claim, status_value="lost", reason=reason)

            losing_team = team_by_id.get(losing_claim.team_id)
            if losing_team and losing_team.owner_user_id:
                db.add(
                    NotificationLog(
                        user_id=losing_team.owner_user_id,
                        user_key=f"user:{losing_team.owner_user_id}",
                        alert_type="WAIVER",
                        title="Waiver claim not awarded",
                        body=f"{losing_team.name} did not win {add_player.name} ({reason}).",
                        payload={
                            "league_id": league_id,
                            "claim_id": losing_claim.id,
                            "team_id": losing_team.id,
                            "player_id": losing_claim.add_player_id,
                            "batch_key": batch_key,
                            "reason": reason,
                        },
                    )
                )

    won_count = sum(1 for row in results if row.status == "won")
    lost_count = sum(1 for row in results if row.status == "lost")
    invalid_count = sum(1 for row in results if row.status == "invalid")

    _emit_waiver_event(
        db,
        league_id=league_id,
        event_type="waiver.process.completed",
        payload={
            "batch_key": batch_key,
            "processed_count": len(results),
            "won_count": won_count,
            "lost_count": lost_count,
            "invalid_count": invalid_count,
            "mode": waiver_mode,
        },
    )

    return WaiverProcessExecutionResult(
        response=WaiverProcessResponse(
            batch_key=batch_key,
            processed_count=len(results),
            won_count=won_count,
            lost_count=lost_count,
            invalid_count=invalid_count,
            data=results,
        )
    )
