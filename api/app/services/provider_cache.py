from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState


def scope_dict_to_key(scope: dict[str, object] | None = None) -> str:
    if not scope:
        return "global"
    return json.dumps(scope, sort_keys=True, separators=(",", ":"))


def get_sync_state(db: Session, provider: str, feed: str, scope_key: str) -> ProviderSyncState | None:
    stmt = select(ProviderSyncState).where(
        ProviderSyncState.provider == provider,
        ProviderSyncState.feed == feed,
        ProviderSyncState.scope_key == scope_key,
    )
    return db.scalar(stmt)


def get_or_create_sync_state(db: Session, provider: str, feed: str, scope_key: str) -> ProviderSyncState:
    state = get_sync_state(db, provider, feed, scope_key)
    if state:
        return state
    state = ProviderSyncState(provider=provider, feed=feed, scope_key=scope_key)
    db.add(state)
    db.flush()
    return state


def is_sync_state_stale(state: ProviderSyncState | None, now: datetime | None = None) -> bool:
    if state is None or state.expires_at is None:
        return True
    expires_at = state.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    now_utc = now or datetime.now(timezone.utc)
    return expires_at <= now_utc


def _resolve_ttl_days(ttl_days: int | None = None) -> int:
    if ttl_days and ttl_days > 0:
        return ttl_days
    return max(1, settings.provider_default_cache_ttl_days)


def mark_sync_attempt(
    db: Session,
    *,
    state: ProviderSyncState,
    status: str,
    error_message: str | None = None,
    ttl_days: int | None = None,
) -> ProviderSyncState:
    now = datetime.now(timezone.utc)
    state.last_attempted_at = now
    state.status = status
    state.error_message = error_message

    if status == "ready":
        ttl = _resolve_ttl_days(ttl_days)
        state.last_success_at = now
        state.expires_at = now + timedelta(days=ttl)
        state.consecutive_failures = 0
    elif status == "failed":
        state.consecutive_failures = (state.consecutive_failures or 0) + 1

    db.add(state)
    db.flush()
    return state


def ensure_feed_fresh(
    db: Session,
    *,
    provider: str,
    feed: str,
    scope: dict[str, object] | None,
    refresh_fn: Callable[[], object],
    ttl_days: int | None = None,
    force_refresh: bool = False,
) -> tuple[bool, ProviderSyncState]:
    scope_key = scope_dict_to_key(scope)
    state = get_or_create_sync_state(db, provider, feed, scope_key)

    if not force_refresh and not is_sync_state_stale(state):
        return False, state

    mark_sync_attempt(db, state=state, status="syncing")

    try:
        refresh_fn()
        mark_sync_attempt(db, state=state, status="ready", ttl_days=ttl_days)
        return True, state
    except Exception as exc:
        mark_sync_attempt(db, state=state, status="failed", error_message=str(exc))
        raise
