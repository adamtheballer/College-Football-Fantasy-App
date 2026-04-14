from typing import Any

import httpx

from collegefootballfantasy_api.app.core.config import settings


class SportsDataClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.sportsdata_api_key
        self.base_url = (base_url or settings.sportsdata_base_url).rstrip("/")

    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise RuntimeError("SPORTSDATA_API_KEY is not configured")
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_player_stats(self, external_id: str, season: int | None = None, week: int | None = None) -> Any:
        if season is not None and week is not None:
            path = settings.sportsdata_player_stats_week_path.format(season=season, week=week)
            data = self._request(path)
            if isinstance(data, list):
                for row in data:
                    if str(row.get("PlayerID")) == str(external_id):
                        return row
            return {}
        path = settings.sportsdata_player_stats_path.format(external_id=external_id)
        return self._request(path)

    def get_weekly_player_stats(self, season: int, week: int) -> list[dict]:
        path = settings.sportsdata_player_stats_week_path.format(season=season, week=week)
        data = self._request(path)
        if isinstance(data, list):
            return data
        return [data]

    def get_players(self) -> list[dict[str, Any]]:
        data = self._request(settings.sportsdata_players_path)
        if isinstance(data, list):
            return data
        return [data]

    def get_schedule(self, season: int) -> list[dict[str, Any]]:
        path = settings.sportsdata_schedule_season_path.format(season=season)
        data = self._request(path)
        if isinstance(data, list):
            return data
        return [data]

    def get_standings(self, season: int) -> list[dict[str, Any]]:
        path = settings.sportsdata_standings_path.format(season=season)
        data = self._request(path)
        if isinstance(data, list):
            return data
        return [data]

    def get_injuries(self, season: int) -> list[dict[str, Any]]:
        path = settings.sportsdata_injuries_season_path.format(season=season)
        data = self._request(path)
        if isinstance(data, list):
            return data
        return [data]
