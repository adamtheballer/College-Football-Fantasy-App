from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from api.app.api.routes import leagues as league_routes
from api.app.api.routes import mock_drafts as mock_draft_routes
from api.app.core.config import settings
from api.app.db.session import SessionLocal
from api.app.models.draft import Draft
from api.app.models.league import League
from api.app.models.mock_draft_session import MockDraftSession

logger = logging.getLogger(__name__)


@dataclass
class TimeoutTickResult:
    scanned: int = 0
    autopicks: int = 0
    failures: int = 0


class DraftTimeoutRunner:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running or not settings.draft_timeout_runner_enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="draft-timeout-runner")
        logger.info("draft_timeout_runner_started interval_ms=%s", settings.draft_timeout_runner_interval_ms)

    async def stop(self) -> None:
        self._running = False
        task = self._task
        self._task = None
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        logger.info("draft_timeout_runner_stopped")

    async def _loop(self) -> None:
        interval_seconds = max(0.25, settings.draft_timeout_runner_interval_ms / 1000.0)
        while self._running:
            started = datetime.now(timezone.utc)
            try:
                result = await asyncio.to_thread(self._tick_once)
                if result.autopicks or result.failures:
                    logger.info(
                        "draft_timeout_runner_tick scanned=%s autopicks=%s failures=%s",
                        result.scanned,
                        result.autopicks,
                        result.failures,
                    )
            except Exception:
                logger.exception("draft_timeout_runner_tick_failed")

            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            await asyncio.sleep(max(0.01, interval_seconds - elapsed))

    def _tick_once(self) -> TimeoutTickResult:
        result = TimeoutTickResult()
        session: Session = SessionLocal()
        try:
            rows = (
                session.query(League.id)
                .join(Draft, Draft.league_id == League.id)
                .filter(Draft.status.in_(["scheduled", "countdown", "live"]))
                .limit(max(1, int(settings.draft_timeout_batch_limit)))
                .all()
            )
            league_ids = [int(row[0]) for row in rows]
            try:
                mock_rows = (
                    session.query(MockDraftSession.id)
                    .filter(MockDraftSession.status.in_(["scheduled", "countdown", "live"]))
                    .limit(max(1, int(settings.draft_timeout_batch_limit)))
                    .all()
                )
                mock_ids = [int(row[0]) for row in mock_rows]
            except ProgrammingError:
                session.rollback()
                mock_ids = []
            result.scanned = len(league_ids) + len(mock_ids)

            for league_id in league_ids:
                try:
                    league = session.get(League, league_id)
                    if league is None:
                        continue
                    changed = league_routes._autopick_timed_out_current_team(  # noqa: SLF001
                        session,
                        league=league,
                        current_user=None,
                    )
                    if changed:
                        session.commit()
                        result.autopicks += 1
                except Exception:
                    session.rollback()
                    result.failures += 1
                    logger.exception("draft_timeout_runner_autopick_failed league_id=%s", league_id)
            for session_id in mock_ids:
                try:
                    session_row = session.get(MockDraftSession, session_id)
                    if session_row is None:
                        continue
                    changed = mock_draft_routes._autopick_timed_out_current_seat(  # noqa: SLF001
                        session,
                        session_row=session_row,
                    )
                    if changed:
                        session.commit()
                        result.autopicks += 1
                except Exception:
                    session.rollback()
                    result.failures += 1
                    logger.exception("draft_timeout_runner_autopick_failed mock_draft_id=%s", session_id)
        finally:
            session.close()
        return result


draft_timeout_runner = DraftTimeoutRunner()
