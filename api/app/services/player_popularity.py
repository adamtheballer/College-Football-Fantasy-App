"""Daily published popularity aggregates for league roster and waiver reads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_player_event import LeaguePlayerEvent
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.player_popularity_snapshot import (
    PlayerHotPickupMetric,
    PlayerPopularityMetric,
    PlayerPopularitySnapshot,
)
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.services.league_player_history import (
    EVENT_FREE_AGENT_ADDED,
    EVENT_WAIVER_CLAIMED,
)
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter

DAILY_SNAPSHOT_HOUR_UTC = 6
HOT_PICKUP_WINDOWS = (24, 168)


@dataclass(frozen=True)
class PlayerPopularityRead:
    rostered_percent: float | None
    start_percent: float | None


@dataclass(frozen=True)
class PlayerPopularitySnapshotRead:
    as_of: datetime | None
    coverage_started_at: datetime | None
    status: str


def _utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _scheduled_snapshot_date(now: datetime) -> date:
    now = _utc(now)
    return now.date() if now.hour >= DAILY_SNAPSHOT_HOUR_UTC else (now - timedelta(days=1)).date()


def _eligible_league_ids(db: Session, season: int) -> list[int]:
    """Use actual completed league drafts; mock drafts live in a separate table.

    The production schema has no demo/test flag.  We therefore do not invent a
    brittle name-based exclusion.  Only current-season, invite-only custom
    leagues with an explicitly completed draft qualify.
    """
    return [
        int(league_id)
        for (league_id,) in (
            db.query(League.id)
            .join(Draft, Draft.league_id == League.id)
            .filter(
                League.season_year == season,
                League.platform == "custom",
                League.status.in_(("post_draft", "active")),
                Draft.status == "completed",
            )
            .distinct()
            .all()
        )
    ]


def _coverage_started_at(db: Session, *, season: int, league_ids: list[int]) -> datetime | None:
    if not league_ids:
        return None
    return (
        db.query(func.min(LeaguePlayerEvent.occurred_at))
        .filter(
            LeaguePlayerEvent.season == season,
            LeaguePlayerEvent.league_id.in_(league_ids),
            LeaguePlayerEvent.event_type.in_((EVENT_FREE_AGENT_ADDED, EVENT_WAIVER_CLAIMED)),
        )
        .scalar()
    )


def publish_player_popularity_snapshot(
    db: Session,
    *,
    season: int,
    now: datetime | None = None,
) -> PlayerPopularitySnapshot:
    """Reconcile and publish one immutable daily aggregate snapshot.

    Existing published rows are never rewritten.  A failed current run cannot
    erase a prior successful day's data, and league page reads always select
    the latest published snapshot.
    """
    now = _utc(now)
    snapshot_date = _scheduled_snapshot_date(now)
    existing = (
        db.query(PlayerPopularitySnapshot)
        .filter(
            PlayerPopularitySnapshot.season == season,
            PlayerPopularitySnapshot.snapshot_date == snapshot_date,
        )
        .with_for_update()
        .one_or_none()
    )
    if existing and existing.status == "published":
        return existing
    if existing is None:
        snapshot = PlayerPopularitySnapshot(season=season, snapshot_date=snapshot_date, status="running")
        db.add(snapshot)
        try:
            db.flush()
        except IntegrityError:
            # A second worker may have inserted the day's row just before our
            # insert.  Re-read it rather than failing a lifecycle iteration or
            # publishing two conflicting versions.
            db.rollback()
            winner = (
                db.query(PlayerPopularitySnapshot)
                .filter(
                    PlayerPopularitySnapshot.season == season,
                    PlayerPopularitySnapshot.snapshot_date == snapshot_date,
                )
                .one()
            )
            return winner
    else:
        snapshot = existing
        db.query(PlayerPopularityMetric).filter(PlayerPopularityMetric.snapshot_id == snapshot.id).delete(synchronize_session=False)
        db.query(PlayerHotPickupMetric).filter(PlayerHotPickupMetric.snapshot_id == snapshot.id).delete(synchronize_session=False)
        snapshot.status = "running"
        snapshot.failure_reason = None
        snapshot.published_at = None
        db.flush()

    snapshot_id = snapshot.id
    try:
        league_ids = _eligible_league_ids(db, season)
        # The canonical pool is the same source of truth used by draft and
        # waiver reads.  Populate zero rows too, so a player with no ownership
        # can render a truthful 0% once a cohort exists.
        from collegefootballfantasy_api.app.models.player import Player

        player_ids = [
            int(player_id)
            for (player_id,) in db.query(Player.id).filter(canonical_fantasy_player_filter(season)).all()
        ]
        denominator = len(league_ids)
        roster_counts: dict[int, int] = {}
        starter_counts: dict[int, int] = {}
        start_sample_counts: dict[int, int] = {}
        if league_ids:
            roster_counts = {
                int(player_id): int(count)
                for player_id, count in (
                    db.query(RosterEntry.player_id, func.count(func.distinct(RosterEntry.league_id)))
                    .filter(RosterEntry.league_id.in_(league_ids))
                    .group_by(RosterEntry.player_id)
                    .all()
                )
            }
            # Start % is based exclusively on the persisted kickoff-frozen
            # snapshot, not mutable roster slots or a client's local lineup.
            starter_counts = {
                int(player_id): int(count)
                for player_id, count in (
                    db.query(LineupWeekSnapshot.player_id, func.count(func.distinct(LineupWeekSnapshot.league_id)))
                    .filter(
                        LineupWeekSnapshot.league_id.in_(league_ids),
                        LineupWeekSnapshot.season == season,
                        LineupWeekSnapshot.week == calendar_cfb_week(season, now),
                        LineupWeekSnapshot.is_starter.is_(True),
                    )
                    .group_by(LineupWeekSnapshot.player_id)
                    .all()
                )
            }
            start_sample_counts = {
                int(player_id): int(count)
                for player_id, count in (
                    db.query(LineupWeekSnapshot.player_id, func.count(func.distinct(LineupWeekSnapshot.league_id)))
                    .filter(
                        LineupWeekSnapshot.league_id.in_(league_ids),
                        LineupWeekSnapshot.season == season,
                        LineupWeekSnapshot.week == calendar_cfb_week(season, now),
                        LineupWeekSnapshot.locked_at.isnot(None),
                    )
                    .group_by(LineupWeekSnapshot.player_id)
                    .all()
                )
            }
        db.add_all(
            [
                PlayerPopularityMetric(
                    snapshot_id=snapshot.id,
                    player_id=player_id,
                    eligible_league_count=denominator,
                    rostered_league_count=roster_counts.get(player_id, 0),
                    started_league_count=starter_counts.get(player_id, 0),
                    start_sample_league_count=start_sample_counts.get(player_id, 0),
                )
                for player_id in player_ids
            ]
        )
        coverage_started_at = _coverage_started_at(db, season=season, league_ids=league_ids)
        for window_hours in HOT_PICKUP_WINDOWS:
            cutoff = now - timedelta(hours=window_hours)
            rows = (
                db.query(
                    LeaguePlayerEvent.player_id,
                    func.count(func.distinct(LeaguePlayerEvent.league_id)).label("league_count"),
                )
                .filter(
                    LeaguePlayerEvent.season == season,
                    LeaguePlayerEvent.league_id.in_(league_ids or {-1}),
                    LeaguePlayerEvent.event_type.in_((EVENT_FREE_AGENT_ADDED, EVENT_WAIVER_CLAIMED)),
                    LeaguePlayerEvent.occurred_at >= cutoff,
                    LeaguePlayerEvent.occurred_at <= now,
                )
                .group_by(LeaguePlayerEvent.player_id)
                .all()
            )
            db.add_all(
                [
                    PlayerHotPickupMetric(
                        snapshot_id=snapshot.id,
                        player_id=int(player_id),
                        window_hours=window_hours,
                        pickup_league_count=int(league_count),
                    )
                    for player_id, league_count in rows
                ]
            )
        snapshot.coverage_started_at = coverage_started_at
        snapshot.status = "published"
        snapshot.published_at = now
        db.commit()
        return snapshot
    except Exception as exc:
        db.rollback()
        # Best-effort operational visibility.  The reader will still return
        # the previous published day rather than manufacturing a new result.
        failed = db.get(PlayerPopularitySnapshot, snapshot_id)
        if failed is not None and failed.status != "published":
            failed.status = "failed"
            failed.failure_reason = str(exc)[:500]
            db.commit()
        raise


def run_due_player_popularity_snapshot(db: Session, *, season: int, now: datetime | None = None) -> dict[str, int | str]:
    snapshot = publish_player_popularity_snapshot(db, season=season, now=now)
    return {"snapshot_id": snapshot.id, "status": snapshot.status, "season": season}


def latest_player_popularity_snapshot(db: Session, *, season: int) -> PlayerPopularitySnapshot | None:
    return (
        db.query(PlayerPopularitySnapshot)
        .filter(PlayerPopularitySnapshot.season == season, PlayerPopularitySnapshot.status == "published")
        .order_by(PlayerPopularitySnapshot.published_at.desc(), PlayerPopularitySnapshot.id.desc())
        .first()
    )


def player_popularity_for_ids(db: Session, *, season: int, player_ids: set[int]) -> tuple[dict[int, PlayerPopularityRead], PlayerPopularitySnapshotRead]:
    snapshot = latest_player_popularity_snapshot(db, season=season)
    if snapshot is None:
        return {}, PlayerPopularitySnapshotRead(as_of=None, coverage_started_at=None, status="unavailable")
    rows = (
        db.query(PlayerPopularityMetric)
        .filter(PlayerPopularityMetric.snapshot_id == snapshot.id, PlayerPopularityMetric.player_id.in_(player_ids or {-1}))
        .all()
    )
    values: dict[int, PlayerPopularityRead] = {}
    for row in rows:
        if row.eligible_league_count <= 0:
            values[row.player_id] = PlayerPopularityRead(None, None)
            continue
        values[row.player_id] = PlayerPopularityRead(
            rostered_percent=round(100 * row.rostered_league_count / row.eligible_league_count, 1),
            start_percent=(
                round(100 * row.started_league_count / row.eligible_league_count, 1)
                if row.start_sample_league_count > 0
                else None
            ),
        )
    return values, PlayerPopularitySnapshotRead(
        as_of=snapshot.published_at,
        coverage_started_at=snapshot.coverage_started_at,
        status="fresh",
    )


def hot_pickup_player_ids(db: Session, *, season: int, window_hours: int) -> tuple[list[int], PlayerPopularitySnapshotRead]:
    if window_hours not in HOT_PICKUP_WINDOWS:
        raise ValueError("window_hours must be 24 or 168")
    snapshot = latest_player_popularity_snapshot(db, season=season)
    if snapshot is None:
        return [], PlayerPopularitySnapshotRead(as_of=None, coverage_started_at=None, status="unavailable")
    ids = [
        int(player_id)
        for (player_id,) in (
            db.query(PlayerHotPickupMetric.player_id)
            .filter(
                PlayerHotPickupMetric.snapshot_id == snapshot.id,
                PlayerHotPickupMetric.window_hours == window_hours,
            )
            .order_by(PlayerHotPickupMetric.pickup_league_count.desc(), PlayerHotPickupMetric.player_id.asc())
            .all()
        )
    ]
    return ids, PlayerPopularitySnapshotRead(
        as_of=snapshot.published_at,
        coverage_started_at=snapshot.coverage_started_at,
        status="fresh",
    )


def hot_pickup_counts_for_ids(
    db: Session, *, season: int, window_hours: int, player_ids: set[int]
) -> tuple[dict[int, int], PlayerPopularitySnapshotRead]:
    if window_hours not in HOT_PICKUP_WINDOWS:
        raise ValueError("window_hours must be 24 or 168")
    snapshot = latest_player_popularity_snapshot(db, season=season)
    if snapshot is None:
        return {}, PlayerPopularitySnapshotRead(as_of=None, coverage_started_at=None, status="unavailable")
    counts = {
        int(player_id): int(count)
        for player_id, count in (
            db.query(PlayerHotPickupMetric.player_id, PlayerHotPickupMetric.pickup_league_count)
            .filter(
                PlayerHotPickupMetric.snapshot_id == snapshot.id,
                PlayerHotPickupMetric.window_hours == window_hours,
                PlayerHotPickupMetric.player_id.in_(player_ids or {-1}),
            )
            .all()
        )
    }
    return counts, PlayerPopularitySnapshotRead(
        as_of=snapshot.published_at,
        coverage_started_at=snapshot.coverage_started_at,
        status="fresh",
    )
