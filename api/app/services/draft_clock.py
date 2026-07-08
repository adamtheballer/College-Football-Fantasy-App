from __future__ import annotations

from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.draft import Draft


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def draft_timer_seconds(draft: Draft) -> int:
    return int(draft.clock_seconds or draft.pick_timer_seconds or 90)


def start_pick_clock(draft: Draft, now: datetime | None = None) -> None:
    current_time = now or utc_now()
    seconds = draft_timer_seconds(draft)
    draft.pick_started_at = current_time
    draft.pick_expires_at = current_time + timedelta(seconds=seconds)
    draft.clock_seconds = seconds
    draft.paused_at = None


def ensure_pick_clock(draft: Draft, now: datetime | None = None) -> None:
    if draft.status in {"completed", "cancelled", "paused"}:
        return
    if draft.pick_started_at is None or draft.pick_expires_at is None:
        start_pick_clock(draft, now)


def advance_pick_clock(draft: Draft, now: datetime | None = None) -> None:
    start_pick_clock(draft, now)


def pause_pick_clock(draft: Draft, now: datetime | None = None) -> None:
    current_time = now or utc_now()
    if draft.status == "paused":
        return
    draft.status = "paused"
    draft.paused_at = current_time


def resume_pick_clock(draft: Draft, now: datetime | None = None) -> None:
    current_time = now or utc_now()
    paused_at = normalize_aware(draft.paused_at)
    if paused_at is not None:
        paused_seconds = max(0, int((current_time - paused_at).total_seconds()))
        draft.pause_accumulated_seconds = int(draft.pause_accumulated_seconds or 0) + paused_seconds
        expires_at = normalize_aware(draft.pick_expires_at)
        if expires_at is not None:
            draft.pick_expires_at = expires_at + timedelta(seconds=paused_seconds)
    draft.paused_at = None
    draft.status = "live"


def seconds_remaining(draft: Draft, now: datetime | None = None) -> int | None:
    if draft.status == "paused":
        expires_at = normalize_aware(draft.pick_expires_at)
        paused_at = normalize_aware(draft.paused_at)
        if expires_at is None or paused_at is None:
            return None
        return max(0, int((expires_at - paused_at).total_seconds()))
    expires_at = normalize_aware(draft.pick_expires_at)
    if expires_at is None:
        return None
    return max(0, int((expires_at - (now or utc_now())).total_seconds()))


def clock_expired(draft: Draft, now: datetime | None = None) -> bool:
    if draft.status == "paused":
        return False
    remaining = seconds_remaining(draft, now)
    return remaining is not None and remaining <= 0

