"""Orchestration for the shadow-only ESPN live-scoring poller.

This service deliberately separates short database transactions from provider
I/O.  The worker claims a durable poll, commits, calls ESPN, then opens a new
transaction to persist the immutable response.  That makes retries, leases,
and concurrent worker instances safe without holding database locks over the
network.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.integrations.espn_live_scoring_adapter import (
    EspnLiveProviderError,
    EspnLiveScoringAdapter,
)
from collegefootballfantasy_api.app.services.live_scoring_service import (
    claim_due_espn_poll_states,
    ensure_relevant_espn_poll_states,
    ingest_espn_game_summary,
    ingest_espn_scoreboard,
    record_espn_poll_failure,
    record_espn_provider_outage,
    scoreboard_refresh_due,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EspnPollingResult:
    states_created: int = 0
    scoreboard_games: int = 0
    detail_requests: int = 0
    detail_ingested: int = 0
    failures: int = 0


SessionFactory = Callable[[], Session]


def _adapter() -> EspnLiveScoringAdapter:
    return EspnLiveScoringAdapter(
        base_url=settings.espn_live_scoring_base_url,
        timeout_seconds=settings.espn_live_scoring_timeout_seconds,
    )


def run_espn_shadow_poll_iteration(
    *,
    session_factory: SessionFactory,
    season: int,
    week: int,
    adapter: EspnLiveScoringAdapter | None = None,
) -> EspnPollingResult:
    """Run exactly one safe provider polling iteration.

    The caller must leave ``SCORING_MODE`` in shadow.  This function does not
    write public matchup, standings, waiver, or player-stat read models.
    """
    if not settings.espn_live_scoring_enabled or not settings.scoring_shadow_enabled:
        return EspnPollingResult()
    provider = adapter or _adapter()
    with session_factory() as db:
        states_created = ensure_relevant_espn_poll_states(db, season=season, week=week)
        should_fetch_scoreboard = scoreboard_refresh_due(db, season=season, week=week)
        db.commit()

    scoreboard_games = failures = 0
    if should_fetch_scoreboard:
        # Provider I/O occurs after the transaction above has committed.
        try:
            scoreboard = provider.fetch_scoreboard(season=season, week=week)
        except EspnLiveProviderError as exc:
            logger.warning("espn_scoreboard_poll_failed", extra={"category": exc.category, "status": exc.status_code})
            with session_factory() as db:
                record_espn_provider_outage(
                    db,
                    category=exc.category,
                    message=str(exc),
                    status_code=exc.status_code,
                    retry_after=exc.retry_after,
                )
                db.commit()
            failures += 1
        else:
            with session_factory() as db:
                scoreboard_games = ingest_espn_scoreboard(db, games=scoreboard)
                db.commit()

    with session_factory() as db:
        claims = claim_due_espn_poll_states(db, season=season, week=week)
        db.commit()

    detail_ingested = 0
    for claim in claims:
        try:
            # This is intentionally outside every database transaction.
            summary = provider.fetch_game_summary(
                game_id=claim["game_id"], season=claim["season"], week=claim["week"]
            )
        except EspnLiveProviderError as exc:
            with session_factory() as db:
                record_espn_poll_failure(
                    db,
                    state_id=claim["state_id"],
                    category=exc.category,
                    message=str(exc),
                    status_code=exc.status_code,
                    retry_after=exc.retry_after,
                )
                db.commit()
            failures += 1
            continue
        except Exception as exc:  # noqa: BLE001 - provider boundary is deliberately defensive
            with session_factory() as db:
                record_espn_poll_failure(
                    db,
                    state_id=claim["state_id"],
                    category="UNEXPECTED_PROVIDER_ERROR",
                    message=str(exc),
                )
                db.commit()
            failures += 1
            continue
        with session_factory() as db:
            outcome = ingest_espn_game_summary(db, state_id=claim["state_id"], summary=summary)
            db.commit()
        detail_ingested += outcome["revisions"]

    return EspnPollingResult(
        states_created=states_created,
        scoreboard_games=scoreboard_games,
        detail_requests=len(claims),
        detail_ingested=detail_ingested,
        failures=failures,
    )
