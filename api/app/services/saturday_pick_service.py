from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.saturday_pick import (
    SaturdayPickContest,
    SaturdayPickEntry,
    SaturdayPickPlayer,
)
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.saturday_pick import (
    SaturdayPickContestCreate,
    SaturdayPickContestRead,
    SaturdayPickEntryRead,
    SaturdayPickPlayerRead,
    SaturdayPickSponsorRead,
)


OPEN_STATUSES = {"OPEN", "LIVE"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def get_contest_or_404(db: Session, contest_id: int) -> SaturdayPickContest:
    contest = db.get(SaturdayPickContest, contest_id)
    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saturday Pick 6 contest not found")
    return contest


def sync_contest_lock(db: Session, contest: SaturdayPickContest) -> SaturdayPickContest:
    if contest.status in OPEN_STATUSES and _as_utc(contest.lock_at) <= _now():
        contest.status = "LOCKED"
        contest.locked_at = _now()
        db.add(contest)
        db.commit()
        db.refresh(contest)
    return contest


def _entry_read(entry: SaturdayPickEntry) -> SaturdayPickEntryRead:
    return SaturdayPickEntryRead(
        id=entry.id,
        selected_pick_player_id=entry.selected_pick_player_id,
        submitted_at=entry.submitted_at,
        is_winner=entry.is_winner,
        reward_unlocked_at=entry.reward_unlocked_at,
    )


def serialize_contest(
    db: Session,
    contest: SaturdayPickContest,
    current_user: User | None = None,
) -> SaturdayPickContestRead:
    contest = sync_contest_lock(db, contest)
    rows = (
        db.query(SaturdayPickPlayer)
        .filter(SaturdayPickPlayer.contest_id == contest.id)
        .order_by(SaturdayPickPlayer.sort_order.asc())
        .all()
    )
    entry = None
    if current_user:
        entry = (
            db.query(SaturdayPickEntry)
            .filter(
                SaturdayPickEntry.contest_id == contest.id,
                SaturdayPickEntry.user_id == current_user.id,
            )
            .one_or_none()
        )
    sponsor = None
    if settings.saturday_pick_6_sponsors_enabled and contest.sponsor_name:
        sponsor = SaturdayPickSponsorRead(
            name=contest.sponsor_name,
            logo_url=contest.sponsor_logo_url,
            offer_text=contest.sponsor_offer_text,
            terms=contest.sponsor_terms,
            reward_unlocked=bool(entry and entry.reward_unlocked_at),
            # A reward code must remain private until the entry wins.
            code=contest.sponsor_code if entry and entry.reward_unlocked_at else None,
            url=contest.sponsor_url,
        )
    return SaturdayPickContestRead(
        id=contest.id,
        season=contest.season,
        week_number=contest.week_number,
        title=contest.title,
        contest_position=contest.contest_position,
        status=contest.status,
        lock_at=contest.lock_at,
        players=[
            SaturdayPickPlayerRead(
                id=row.id,
                player_id=row.player_id,
                canonical_position=row.canonical_position,
                player_name=row.player_name_snapshot,
                school=row.school_snapshot,
                opponent=row.opponent_snapshot,
                game_id=row.game_id,
                game_time=row.game_time,
                # Third-party player headshots are intentionally never returned.
                image_url=None,
                projected_points=row.projected_points,
                live_points=row.live_points,
                final_points=row.final_points,
                scoring_status=row.scoring_status,
                sort_order=row.sort_order,
            )
            for row in rows
        ],
        entry=_entry_read(entry) if entry else None,
        sponsor=sponsor,
    )


def current_contest(db: Session, season: int, week_number: int) -> SaturdayPickContest:
    contest = (
        db.query(SaturdayPickContest)
        .filter(SaturdayPickContest.season == season, SaturdayPickContest.week_number == week_number)
        .one_or_none()
    )
    if not contest or contest.status == "DRAFT":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Saturday Pick 6 contest is published")
    return contest


def create_contest(
    db: Session, payload: SaturdayPickContestCreate, current_user: User
) -> SaturdayPickContest:
    if len({row.player_id for row in payload.featured_players}) != 6:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Six distinct players are required")
    if (
        db.query(SaturdayPickContest)
        .filter(
            SaturdayPickContest.season == payload.season,
            SaturdayPickContest.week_number == payload.week_number,
        )
        .first()
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contest already exists for this week")

    players = {row.id: row for row in db.query(Player).filter(Player.id.in_([p.player_id for p in payload.featured_players])).all()}
    if len(players) != 6:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Every featured player must exist")
    if any(players[row.player_id].position != payload.contest_position for row in payload.featured_players):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Featured player position does not match contest")
    earliest_game = min(_as_utc(row.game_time) for row in payload.featured_players)
    if _as_utc(payload.lock_at) > earliest_game:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Pick lock cannot be later than the first featured game")

    contest = SaturdayPickContest(
        season=payload.season,
        week_number=payload.week_number,
        title=payload.title.strip(),
        contest_position=payload.contest_position,
        lock_at=payload.lock_at,
        sponsor_name=payload.sponsor_name or settings.saturday_pick_6_sponsor_name,
        sponsor_logo_url=payload.sponsor_logo_url,
        sponsor_offer_text=payload.sponsor_offer_text or settings.saturday_pick_6_sponsor_offer_text,
        sponsor_code=payload.sponsor_code,
        sponsor_url=payload.sponsor_url or settings.saturday_pick_6_sponsor_url,
        sponsor_terms=payload.sponsor_terms,
        created_by_user_id=current_user.id,
    )
    db.add(contest)
    db.flush()
    for index, featured in enumerate(payload.featured_players, start=1):
        player = players[featured.player_id]
        db.add(
            SaturdayPickPlayer(
                contest_id=contest.id,
                player_id=player.id,
                canonical_position=player.position,
                player_name_snapshot=player.name,
                school_snapshot=player.school,
                opponent_snapshot=featured.opponent.strip(),
                game_id=featured.game_id,
                game_time=featured.game_time,
                projected_points=featured.projected_points,
                sort_order=index,
            )
        )
    db.commit()
    db.refresh(contest)
    return contest


def publish_contest(db: Session, contest: SaturdayPickContest, lock_at: datetime | None = None) -> SaturdayPickContest:
    if contest.status not in {"DRAFT", "OPEN"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only a draft contest can be published")
    if lock_at is not None:
        contest.lock_at = lock_at
    contest.status = "OPEN"
    contest.published_at = _now()
    db.add(contest)
    db.commit()
    db.refresh(contest)
    return sync_contest_lock(db, contest)


def save_entry(
    db: Session, contest: SaturdayPickContest, selected_pick_player_id: int, current_user: User
) -> SaturdayPickEntry:
    contest = sync_contest_lock(db, contest)
    if contest.status not in OPEN_STATUSES or _as_utc(contest.lock_at) <= _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Saturday Pick 6 contest is locked")
    selected = (
        db.query(SaturdayPickPlayer)
        .filter(
            SaturdayPickPlayer.id == selected_pick_player_id,
            SaturdayPickPlayer.contest_id == contest.id,
        )
        .one_or_none()
    )
    if not selected:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a featured player")
    entry = (
        db.query(SaturdayPickEntry)
        .filter(SaturdayPickEntry.contest_id == contest.id, SaturdayPickEntry.user_id == current_user.id)
        .one_or_none()
    )
    if entry:
        entry.selected_pick_player_id = selected.id
        entry.submitted_at = _now()
    else:
        entry = SaturdayPickEntry(
            contest_id=contest.id,
            user_id=current_user.id,
            selected_pick_player_id=selected.id,
            submitted_at=_now(),
        )
        db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def clear_entry(db: Session, contest: SaturdayPickContest, current_user: User) -> None:
    """Remove an unlocked pick as soon as the manager elects to change it.

    This deliberately does not retain a hidden fallback selection: after pressing
    Change Pick, the manager must explicitly select and lock a replacement.
    """
    contest = sync_contest_lock(db, contest)
    if contest.status not in OPEN_STATUSES or _as_utc(contest.lock_at) <= _now():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This Saturday Pick 6 contest is locked")
    entry = (
        db.query(SaturdayPickEntry)
        .filter(SaturdayPickEntry.contest_id == contest.id, SaturdayPickEntry.user_id == current_user.id)
        .one_or_none()
    )
    if entry:
        db.delete(entry)
        db.commit()
