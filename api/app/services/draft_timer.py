from datetime import datetime, timedelta, timezone


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def start_pick_timer(session: object, now: datetime) -> None:
    now_utc = _as_utc(now) or datetime.now(timezone.utc)
    pick_timer_seconds = int(getattr(session, "pick_timer_seconds", 0) or 0)
    setattr(session, "current_pick_started_at", now_utc)
    setattr(session, "current_pick_expires_at", now_utc + timedelta(seconds=max(0, pick_timer_seconds)))


def reset_pick_timer_after_pick(session: object, now: datetime) -> None:
    start_pick_timer(session, now)


def seconds_remaining(session: object, now: datetime) -> int | None:
    expires_at = _as_utc(getattr(session, "current_pick_expires_at", None))
    if expires_at is None:
        return None
    now_utc = _as_utc(now) or datetime.now(timezone.utc)
    return max(0, int((expires_at - now_utc).total_seconds() + 0.999))


def is_timer_expired(session: object, now: datetime) -> bool:
    remaining = seconds_remaining(session, now)
    return remaining is not None and remaining <= 0


def clear_timer_on_completion(session: object) -> None:
    setattr(session, "current_pick_started_at", None)
    setattr(session, "current_pick_expires_at", None)


def transition_intermission_if_needed(session: object, now: datetime) -> bool:
    status = str(getattr(session, "status", ""))
    if status != "intermission":
        return False
    ends_at = _as_utc(getattr(session, "intermission_ends_at", None))
    now_utc = _as_utc(now) or datetime.now(timezone.utc)
    if ends_at is None or ends_at > now_utc:
        return False
    setattr(session, "status", "live")
    setattr(session, "started_at", now_utc)
    start_pick_timer(session, now_utc)
    return True
