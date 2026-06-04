from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.app.core.config import settings
from api.app.db.session import SessionLocal
from api.app.models.domain_event import DomainEvent
from api.app.services.draft_realtime import draft_realtime_manager

logger = logging.getLogger(__name__)

EVENT_SCHEMA_VERSION = 1


def _event_legacy_name(event_type: str) -> str:
    mapping = {
        "draft.room.snapshot": "draft_room_ready",
        "draft.room.updated": "draft_room_updated",
        "draft.pick.made": "draft_pick_made",
        "draft.player_pool.updated": "draft_player_pool_updated",
    }
    return mapping.get(event_type, event_type.replace(".", "_"))


@dataclass
class RealtimeRelayStatus:
    enabled: bool
    running: bool
    last_seen_seq: int
    last_poll_at: datetime | None
    last_broadcast_at: datetime | None
    total_broadcast_events: int
    last_error: str | None


class DraftRealtimeRelay:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_seen_seq = 0
        self._last_poll_at: datetime | None = None
        self._last_broadcast_at: datetime | None = None
        self._total_broadcast_events = 0
        self._last_error: str | None = None

    @staticmethod
    def _db_is_postgres() -> bool:
        return settings.database_url.startswith("postgresql")

    def _initialize_cursor(self) -> int:
        with SessionLocal() as db:
            latest = db.query(DomainEvent.id).order_by(DomainEvent.id.desc()).first()
            if not latest:
                return 0
            return int(latest[0])

    def _fetch_events_after(self, seq: int, limit: int) -> list[DomainEvent]:
        with SessionLocal() as db:
            return (
                db.query(DomainEvent)
                .filter(DomainEvent.id > seq)
                .order_by(DomainEvent.id.asc())
                .limit(max(1, min(limit, 1000)))
                .all()
            )

    async def start(self) -> None:
        if not settings.realtime_relay_enabled:
            logger.info("realtime relay disabled by config")
            return
        if not self._db_is_postgres():
            logger.info("realtime relay skipped (non-postgres backend)")
            return
        if self._task is not None and not self._task.done():
            return
        self._stop = asyncio.Event()
        self._last_error = None
        if settings.realtime_relay_start_from_latest:
            try:
                self._last_seen_seq = await asyncio.to_thread(self._initialize_cursor)
            except Exception as exc:
                # Keep API startup healthy even when relay backend is unreachable.
                self._last_error = str(exc)[:500]
                logger.exception("realtime relay failed to initialize cursor; skipping relay start")
                return
        self._task = asyncio.create_task(self._run(), name="draft-realtime-relay")
        logger.info("realtime relay started with cursor=%s", self._last_seen_seq)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        try:
            await self._task
        except Exception:
            logger.exception("realtime relay stopped with error")
        finally:
            self._task = None

    async def _run(self) -> None:
        poll_interval = max(0.05, float(settings.realtime_relay_poll_interval_ms) / 1000.0)
        batch_size = max(1, int(settings.realtime_relay_batch_size))
        while not self._stop.is_set():
            try:
                rows = await asyncio.to_thread(self._fetch_events_after, self._last_seen_seq, batch_size)
                self._last_poll_at = datetime.now(timezone.utc)
                if rows:
                    for row in rows:
                        occurred_at = row.occurred_at
                        if occurred_at and occurred_at.tzinfo is None:
                            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
                        await draft_realtime_manager.broadcast(
                            row.league_id,
                            event=_event_legacy_name(row.event_type),
                            payload=row.payload or {},
                            event_id=f"evt_{row.id}",
                            event_type=row.event_type,
                            seq=row.id,
                            schema_version=row.schema_version or EVENT_SCHEMA_VERSION,
                            entity_type=row.entity_type,
                            entity_id=row.entity_id,
                            occurred_at=occurred_at,
                        )
                        self._last_seen_seq = int(row.id)
                        self._last_broadcast_at = datetime.now(timezone.utc)
                        self._total_broadcast_events += 1
                    continue
            except Exception as exc:
                self._last_error = str(exc)[:500]
                logger.exception("realtime relay poll loop error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=poll_interval)
            except TimeoutError:
                pass

    def status(self) -> RealtimeRelayStatus:
        running = self._task is not None and not self._task.done()
        return RealtimeRelayStatus(
            enabled=bool(settings.realtime_relay_enabled and self._db_is_postgres()),
            running=running,
            last_seen_seq=self._last_seen_seq,
            last_poll_at=self._last_poll_at,
            last_broadcast_at=self._last_broadcast_at,
            total_broadcast_events=self._total_broadcast_events,
            last_error=self._last_error,
        )


draft_realtime_relay = DraftRealtimeRelay()
