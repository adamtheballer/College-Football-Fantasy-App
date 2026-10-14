from datetime import datetime, timedelta, timezone

NAME_CHANGE_INTERVAL = timedelta(hours=168)


def next_name_change_at(last_successful_change: datetime | None) -> datetime | None:
    if last_successful_change is None:
        return None
    # Stored naive values represent UTC. Always add elapsed hours in UTC,
    # including when a caller supplies a timezone crossing a DST boundary.
    aware = last_successful_change.replace(tzinfo=timezone.utc) if last_successful_change.tzinfo is None else last_successful_change
    return aware.astimezone(timezone.utc) + NAME_CHANGE_INTERVAL
