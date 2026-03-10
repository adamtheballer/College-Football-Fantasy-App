from __future__ import annotations

from typing import Any

import httpx

from collegefootballfantasy_api.app.core.config import settings


class OddsApiClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.odds_api_key
        self.base_url = (base_url or settings.odds_base_url).rstrip("/")

    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise RuntimeError("ODDS_API_KEY is not configured")
        url = f"{self.base_url}/{path.lstrip('/')}"
        params = params or {}
        params["apiKey"] = self.api_key
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_odds(
        self,
        sport: str = "americanfootball_ncaaf",
        regions: str = "us",
        markets: str = "spreads,totals",
        odds_format: str = "american",
        date_format: str = "iso",
    ) -> list[dict[str, Any]]:
        data = self._request(
            f"sports/{sport}/odds",
            params={
                "regions": regions,
                "markets": markets,
                "oddsFormat": odds_format,
                "dateFormat": date_format,
            },
        )
        if isinstance(data, list):
            return data
        return [data]
