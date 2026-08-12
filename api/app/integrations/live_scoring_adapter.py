"""Provider boundary for the live-scoring ingest pipeline.

Adapters only translate a previously fetched provider payload.  They do not
perform HTTP requests and they never write score read models.  Network clients
belong outside database transactions; the caller persists the returned event
through ``live_scoring_service.record_provider_event``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from collegefootballfantasy_api.app.services.live_scoring_service import ProviderEventInput


class ProviderPayloadError(ValueError):
    """A provider response cannot be safely represented as a scoring event."""


class LiveScoringProviderAdapter(Protocol):
    """Strict provider-to-canonical event contract used by live scoring only."""

    provider: str
    feed: str

    def normalize_event(self, payload: Mapping[str, Any]) -> ProviderEventInput:
        """Return one fully identified, non-secret raw event from a payload."""


@dataclass(frozen=True)
class FrozenPayloadAdapter:
    """Minimal fixture adapter for contract tests and historical replay.

    The implementation intentionally accepts only a normalized envelope.  A
    real SportsData adapter can be added later behind the same protocol, with
    frozen fixture coverage before it is enabled.
    """

    provider: str = "fixture"
    feed: str = "player_game_stats"

    def normalize_event(self, payload: Mapping[str, Any]) -> ProviderEventInput:
        event_id = payload.get("event_id")
        provider_player_id = payload.get("provider_player_id")
        provider_game_id = payload.get("provider_game_id")
        stats = payload.get("stats")
        if not all(isinstance(value, str) and value for value in (event_id, provider_player_id, provider_game_id)):
            raise ProviderPayloadError("fixture scoring payload requires event_id, provider_player_id, and provider_game_id")
        if not isinstance(stats, Mapping):
            raise ProviderPayloadError("fixture scoring payload requires object stats")
        return ProviderEventInput(
            provider=self.provider,
            feed=self.feed,
            endpoint_type="player_game_stats",
            provider_event_id=event_id,
            provider_player_id=provider_player_id,
            provider_game_id=provider_game_id,
            provider_revision=str(payload.get("provider_revision")) if payload.get("provider_revision") is not None else None,
            season=payload.get("season") if isinstance(payload.get("season"), int) else None,
            week=payload.get("week") if isinstance(payload.get("week"), int) else None,
            payload={"stats": dict(stats), "status": payload.get("status")},
        )
