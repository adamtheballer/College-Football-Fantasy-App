"""Backfill the auditable CFB Fantasy career activity timeline.

The script reads existing finalized league records and writes only immutable,
idempotent ``user_career_events`` entries.  It is deliberately dry-run by
default: use ``--apply`` only after reviewing the emitted aggregate summary.
It never changes matchups, standings, rosters, scores, or league state.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from collegefootballfantasy_api.app.models.career import UserCareerEvent
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.mock_draft import MockDraft
from collegefootballfantasy_api.app.models.postseason import PostseasonFinalStanding
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.core.config import settings


FINAL_MATCHUP_STATUSES = {"final", "completed", "complete", "stat_corrected"}
PROCESSED_TRADE_STATUSES = {"processed", "complete", "completed"}


@dataclass(frozen=True)
class PlannedEvent:
    user_id: int
    event_type: str
    source_key: str
    title: str
    occurred_at: datetime
    league_id: int | None = None
    team_id: int | None = None
    matchup_id: int | None = None
    trade_id: int | None = None
    draft_id: int | None = None
    season: int | None = None
    week: int | None = None
    metadata: dict | None = None


def _occurred_at(value: datetime | None) -> datetime:
    return value or datetime.now(timezone.utc)


def build_reconciliation_plan(db: Session) -> list[PlannedEvent]:
    """Build the event plan entirely in memory; this function never writes."""
    plan: list[PlannedEvent] = []
    leagues = {row.id: row for row in db.query(League).all()}
    teams = {row.id: row for row in db.query(Team).filter(Team.owner_user_id.is_not(None)).all()}

    for member in db.query(LeagueMember).all():
        league = leagues.get(member.league_id)
        if league is None:
            continue
        plan.append(PlannedEvent(
            user_id=member.user_id,
            event_type="LEAGUE_JOINED",
            source_key=f"career:league-member:{member.id}",
            title=f"Joined {league.name}",
            occurred_at=_occurred_at(member.joined_at or member.created_at),
            league_id=league.id,
            season=league.season_year,
            metadata={"role": member.role},
        ))

    for league in leagues.values():
        if league.commissioner_user_id is None:
            continue
        plan.append(PlannedEvent(
            user_id=league.commissioner_user_id,
            event_type="LEAGUE_CREATED",
            source_key=f"career:league-created:{league.id}:user:{league.commissioner_user_id}",
            title=f"Created {league.name}",
            occurred_at=_occurred_at(league.created_at),
            league_id=league.id,
            season=league.season_year,
        ))

    for draft in db.query(Draft).filter(Draft.status == "completed").all():
        for team in teams.values():
            if team.league_id != draft.league_id:
                continue
            plan.append(PlannedEvent(
                user_id=team.owner_user_id,
                event_type="OFFICIAL_DRAFT_COMPLETED",
                source_key=f"career:official-draft:{draft.id}:team:{team.id}",
                title="Completed official league draft",
                occurred_at=_occurred_at(draft.completed_at or draft.updated_at),
                league_id=draft.league_id,
                team_id=team.id,
                draft_id=draft.id,
            ))

    for mock in db.query(MockDraft).filter(MockDraft.status == "completed").all():
        plan.append(PlannedEvent(
            user_id=mock.owner_user_id,
            event_type="MOCK_DRAFT_COMPLETED",
            source_key=f"career:mock-draft:{mock.id}:user:{mock.owner_user_id}",
            title="Completed mock draft",
            occurred_at=_occurred_at(mock.completed_at or mock.updated_at),
            # ``draft_id`` references the official-draft table, not mock drafts.
            # Keep the mock's stable id in the source key only.
        ))

    for trade in db.query(TradeOffer).filter(func.lower(TradeOffer.status).in_(PROCESSED_TRADE_STATUSES)).all():
        for team_id in {trade.proposing_team_id, trade.receiving_team_id}:
            team = teams.get(team_id)
            if team is None:
                continue
            plan.append(PlannedEvent(
                user_id=team.owner_user_id,
                event_type="TRADE_COMPLETED",
                source_key=f"career:trade-completed:{trade.id}:team:{team.id}",
                title="Completed league trade",
                occurred_at=_occurred_at(trade.processed_at or trade.accepted_at or trade.updated_at),
                league_id=trade.league_id,
                team_id=team.id,
                trade_id=trade.id,
            ))

    for matchup in db.query(Matchup).filter(func.lower(Matchup.status).in_(FINAL_MATCHUP_STATUSES)).all():
        for team_id, own, opponent in (
            (matchup.home_team_id, matchup.home_score, matchup.away_score),
            (matchup.away_team_id, matchup.away_score, matchup.home_score),
        ):
            team = teams.get(team_id)
            if team is None:
                continue
            result = "W" if own > opponent else "L" if own < opponent else "T"
            plan.append(PlannedEvent(
                user_id=team.owner_user_id,
                event_type="MATCHUP_FINALIZED",
                source_key=f"matchup:final:{matchup.id}:team:{team.id}",
                title=f"Week {matchup.week} {result} ({own:.1f}-{opponent:.1f})",
                occurred_at=_occurred_at(matchup.updated_at),
                league_id=matchup.league_id,
                team_id=team.id,
                matchup_id=matchup.id,
                season=matchup.season,
                week=matchup.week,
                metadata={"result": result, "points_for": own, "points_against": opponent},
            ))

    for standing in db.query(PostseasonFinalStanding).all():
        team = teams.get(standing.team_id)
        if team is None:
            continue
        title = "Won league championship" if standing.final_place == 1 else f"Finished #{standing.final_place} in playoffs"
        plan.append(PlannedEvent(
            user_id=team.owner_user_id,
            event_type="POSTSEASON_FINALIZED",
            source_key=f"career:postseason-final:{standing.id}:team:{team.id}",
            title=title,
            occurred_at=_occurred_at(standing.finalized_at),
            league_id=standing.league_id,
            team_id=team.id,
            season=standing.season,
            metadata={"final_place": standing.final_place, "result": standing.postseason_result},
        ))
    return plan


def reconcile(db: Session, *, apply: bool) -> dict:
    plan = build_reconciliation_plan(db)
    keys = {row.source_key for row in plan}
    existing_keys = {
        row[0] for row in db.query(UserCareerEvent.source_key).filter(UserCareerEvent.source_key.in_(keys)).all()
    } if keys else set()
    missing = [row for row in plan if row.source_key not in existing_keys]
    summary = {
        "mode": "apply" if apply else "dry-run",
        "planned": len(plan),
        "would_create": len(missing),
        "already_recorded": len(plan) - len(missing),
        "created": 0,
        "event_types": dict(sorted(Counter(row.event_type for row in plan).items())),
        "database_writes": 0,
    }
    if not apply:
        return summary
    try:
        for row in missing:
            db.add(UserCareerEvent(
                user_id=row.user_id,
                event_type=row.event_type,
                source_key=row.source_key,
                title=row.title,
                occurred_at=row.occurred_at,
                league_id=row.league_id,
                team_id=row.team_id,
                matchup_id=row.matchup_id,
                trade_id=row.trade_id,
                draft_id=row.draft_id,
                season=row.season,
                week=row.week,
                metadata_json=row.metadata or {},
            ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    summary["created"] = len(missing)
    summary["database_writes"] = len(missing)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=settings.database_url, help="SQLAlchemy database URL")
    parser.add_argument("--apply", action="store_true", help="Write missing events transactionally (dry run is default)")
    args = parser.parse_args()
    engine = create_engine(args.database_url)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        print(json.dumps(reconcile(db, apply=args.apply), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
