from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scheduled_league_job import ScheduledLeagueJob
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.services.admin_actions import append_admin_action
from collegefootballfantasy_api.app.services.draft_realtime import draft_realtime_manager
from collegefootballfantasy_api.app.services.realtime_relay import draft_realtime_relay

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/live")
def ops_liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ops_readiness(
    db: Session = Depends(get_db),
) -> dict:
    db.execute(text("SELECT 1"))
    relay = draft_realtime_relay.status()
    realtime = await draft_realtime_manager.connection_stats()
    return {
        "status": "ready",
        "database": "ok",
        "database_backend": "postgresql" if settings.database_url.startswith("postgresql") else "sqlite",
        "realtime_connections": realtime,
        "realtime_relay": {
            "enabled": relay.enabled,
            "running": relay.running,
            "last_seen_seq": relay.last_seen_seq,
            "last_error": relay.last_error,
        },
    }


@router.get("/overview")
async def ops_overview(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    relay = draft_realtime_relay.status()
    realtime = await draft_realtime_manager.connection_stats()
    queued_jobs = (
        db.query(func.count(ScheduledLeagueJob.id))
        .filter(ScheduledLeagueJob.status == "queued")
        .scalar()
    ) or 0
    failed_jobs = (
        db.query(func.count(ScheduledLeagueJob.id))
        .filter(ScheduledLeagueJob.status == "failed")
        .scalar()
    ) or 0
    pending_waivers = (
        db.query(func.count(WaiverClaim.id))
        .filter(WaiverClaim.status == "pending")
        .scalar()
    ) or 0
    open_trades = (
        db.query(func.count(TradeOffer.id))
        .filter(TradeOffer.status.in_(("open", "pending_review")))
        .scalar()
    ) or 0
    live_drafts = (
        db.query(func.count(Draft.id))
        .filter(Draft.status.in_(("live", "paused")))
        .scalar()
    ) or 0
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jobs": {
            "queued": int(queued_jobs),
            "failed": int(failed_jobs),
        },
        "realtime_connections": realtime,
        "fantasy": {
            "pending_waivers": int(pending_waivers),
            "open_or_review_trades": int(open_trades),
            "live_or_paused_drafts": int(live_drafts),
        },
        "realtime_relay": {
            "enabled": relay.enabled,
            "running": relay.running,
            "last_seen_seq": relay.last_seen_seq,
            "last_poll_at": relay.last_poll_at.isoformat() if relay.last_poll_at else None,
            "last_broadcast_at": relay.last_broadcast_at.isoformat() if relay.last_broadcast_at else None,
            "total_broadcast_events": relay.total_broadcast_events,
            "last_error": relay.last_error,
        },
    }


def _slot_from_position(position: str | None) -> str:
    normalized = (position or "").strip().upper()
    if normalized in {"QB", "RB", "WR", "TE", "K"}:
        return normalized
    return "BENCH"


@router.get("/leagues/{league_id}/draft-integrity")
def draft_integrity_report(
    league_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    draft = db.query(Draft).filter(Draft.league_id == league_id).first()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    picks = (
        db.query(DraftPick, Player)
        .join(Player, Player.id == DraftPick.player_id)
        .filter(DraftPick.draft_id == draft.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )
    roster_rows = db.query(RosterEntry).filter(RosterEntry.league_id == league_id).all()
    roster_by_player = {row.player_id: row for row in roster_rows}
    roster_dupes: dict[int, int] = defaultdict(int)
    for row in roster_rows:
        roster_dupes[row.player_id] += 1

    missing_from_roster: list[dict[str, int | str]] = []
    mismatched_team: list[dict[str, int | str]] = []
    for pick, player in picks:
        roster_entry = roster_by_player.get(pick.player_id)
        if roster_entry is None:
            missing_from_roster.append(
                {
                    "player_id": pick.player_id,
                    "player_name": player.name,
                    "expected_team_id": pick.team_id,
                    "pick_id": pick.id,
                }
            )
            continue
        if roster_entry.team_id != pick.team_id:
            mismatched_team.append(
                {
                    "player_id": pick.player_id,
                    "player_name": player.name,
                    "expected_team_id": pick.team_id,
                    "actual_team_id": roster_entry.team_id,
                    "pick_id": pick.id,
                    "roster_entry_id": roster_entry.id,
                }
            )

    duplicate_players = [
        {"player_id": player_id, "count": count}
        for player_id, count in roster_dupes.items()
        if count > 1
    ]

    return {
        "league_id": league_id,
        "draft_id": draft.id,
        "draft_status": draft.status,
        "totals": {
            "draft_picks": len(picks),
            "roster_entries": len(roster_rows),
            "missing_from_roster": len(missing_from_roster),
            "mismatched_team": len(mismatched_team),
            "duplicate_roster_players": len(duplicate_players),
        },
        "missing_from_roster": missing_from_roster,
        "mismatched_team": mismatched_team,
        "duplicate_roster_players": duplicate_players,
    }


@router.post("/leagues/{league_id}/draft-integrity/repair")
def repair_draft_integrity(
    league_id: int,
    fix_mismatched_team: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    draft = db.query(Draft).filter(Draft.league_id == league_id).first()
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="draft not found")

    picks = (
        db.query(DraftPick, Player)
        .join(Player, Player.id == DraftPick.player_id)
        .filter(DraftPick.draft_id == draft.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )
    if not picks:
        return {
            "league_id": league_id,
            "draft_id": draft.id,
            "created_entries": 0,
            "fixed_mismatched_teams": 0,
            "updated_players": [],
        }

    roster_rows = db.query(RosterEntry).filter(RosterEntry.league_id == league_id).all()
    roster_by_player = {row.player_id: row for row in roster_rows}

    created = 0
    repaired = 0
    updated_players: list[dict[str, int | str]] = []
    for pick, player in picks:
        slot = _slot_from_position(player.position)
        roster_entry = roster_by_player.get(pick.player_id)
        if roster_entry is None:
            roster_entry = RosterEntry(
                league_id=league_id,
                team_id=pick.team_id,
                player_id=pick.player_id,
                slot=slot,
                status="active",
            )
            db.add(roster_entry)
            db.flush()
            roster_by_player[pick.player_id] = roster_entry
            created += 1
            updated_players.append(
                {
                    "player_id": player.id,
                    "player_name": player.name,
                    "action": "created",
                    "team_id": pick.team_id,
                }
            )
            continue

        if fix_mismatched_team and roster_entry.team_id != pick.team_id:
            roster_entry.team_id = pick.team_id
            roster_entry.slot = slot
            roster_entry.status = "active"
            db.add(roster_entry)
            repaired += 1
            updated_players.append(
                {
                    "player_id": player.id,
                    "player_name": player.name,
                    "action": "moved",
                    "team_id": pick.team_id,
                }
            )

    if created or repaired:
        append_admin_action(
            db,
            league_id=league_id,
            actor_user_id=current_user.id,
            action_type="draft.integrity.repair",
            target_type="draft",
            target_id=draft.id,
            metadata={
                "created_entries": created,
                "fixed_mismatched_teams": repaired,
                "fix_mismatched_team": fix_mismatched_team,
            },
        )
        db.commit()
    else:
        db.rollback()

    return {
        "league_id": league_id,
        "draft_id": draft.id,
        "created_entries": created,
        "fixed_mismatched_teams": repaired,
        "updated_players": updated_players,
    }
