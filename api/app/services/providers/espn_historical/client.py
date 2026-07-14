from __future__ import annotations

import time
from typing import Any

import httpx

from collegefootballfantasy_api.app.core.config import settings


class ESPNHistoricalStatsClientError(RuntimeError):
    pass


class ESPNHistoricalStatsClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.espn_historical_stats_base_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": settings.espn_historical_stats_user_agent,
        }

    def athlete_stats_url(self, provider_player_id: str) -> str:
        return f"{self.base_url}/athletes/{provider_player_id}/stats"

    def get_athlete_stats(self, provider_player_id: str) -> dict[str, Any]:
        if not provider_player_id:
            raise ESPNHistoricalStatsClientError("provider_player_id is required")

        url = self.athlete_stats_url(provider_player_id)
        params = {"region": "gb", "lang": "en", "contentorigin": "espn"}
        timeout = settings.espn_historical_stats_timeout_seconds
        max_retries = max(1, settings.espn_historical_stats_max_retries)
        last_error: Exception | None = None

        with httpx.Client(timeout=timeout, headers=self._headers()) as client:
            for attempt in range(max_retries):
                try:
                    response = client.get(url, params=params)
                    if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < max_retries - 1:
                        retry_after = response.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 8)
                        time.sleep(delay)
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if content_type and "json" not in content_type.lower():
                        raise ESPNHistoricalStatsClientError(f"unexpected content-type from ESPN: {content_type}")
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise ESPNHistoricalStatsClientError("ESPN historical stats response was not a JSON object")
                    return payload
                except (httpx.HTTPError, ValueError, ESPNHistoricalStatsClientError) as exc:
                    last_error = exc
                    if attempt < max_retries - 1:
                        time.sleep(min(2**attempt, 8))

        raise ESPNHistoricalStatsClientError(f"ESPN historical stats request failed: {last_error}")
