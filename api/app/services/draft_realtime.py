from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone

from fastapi import WebSocket


class DraftRealtimeManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, league_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[league_id].add(websocket)

    async def disconnect(self, league_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            room = self._connections.get(league_id)
            if not room:
                return
            room.discard(websocket)
            if not room:
                self._connections.pop(league_id, None)

    async def connection_stats(self) -> dict[str, int]:
        async with self._lock:
            room_count = len(self._connections)
            socket_count = sum(len(sockets) for sockets in self._connections.values())
        return {"rooms": room_count, "sockets": socket_count}

    async def broadcast(
        self,
        league_id: int,
        event: str,
        *,
        payload: dict | None = None,
        exclude: Iterable[WebSocket] | None = None,
        event_id: str | None = None,
        event_type: str | None = None,
        entity_type: str = "league",
        entity_id: int | None = None,
        seq: int | None = None,
        schema_version: int = 1,
        occurred_at: datetime | None = None,
    ) -> None:
        async with self._lock:
            sockets = list(self._connections.get(league_id, set()))
        if not sockets:
            return

        excluded = set(exclude or [])
        resolved_at = occurred_at or datetime.now(timezone.utc)
        message = {
            "event": event,
            "event_id": event_id or f"{league_id}:{event}:{int(resolved_at.timestamp() * 1000)}",
            "event_type": event_type or event,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "seq": seq,
            "schema_version": schema_version,
            "league_id": league_id,
            "at": resolved_at.isoformat(),
            "payload": payload or {},
        }

        stale: list[WebSocket] = []
        for socket in sockets:
            if socket in excluded:
                continue
            try:
                await socket.send_json(message)
            except Exception:
                stale.append(socket)

        for socket in stale:
            await self.disconnect(league_id, socket)


draft_realtime_manager = DraftRealtimeManager()
