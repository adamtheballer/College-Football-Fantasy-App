from __future__ import annotations

from datetime import datetime, timezone

from .client import ESPNHistoricalStatsClient
from .parser import parse_player_history
from .schemas import ProviderPlayerHistory


class ESPNHistoricalPlayerStatsProvider:
    def __init__(self, client: ESPNHistoricalStatsClient | None = None) -> None:
        self.client = client or ESPNHistoricalStatsClient()

    def fetch_player_history(self, provider_player_id: str) -> ProviderPlayerHistory:
        fetched_at = datetime.now(timezone.utc)
        payload = self.client.get_athlete_stats(provider_player_id)
        return parse_player_history(
            payload,
            provider_player_id=provider_player_id,
            fetched_at=fetched_at,
            source_url=self.client.athlete_stats_url(provider_player_id),
        )
