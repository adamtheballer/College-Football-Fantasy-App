from __future__ import annotations

import time
from typing import Any

import httpx

from collegefootballfantasy_api.app.core.config import settings


class CFBDClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or settings.cfbd_api_key
        self.base_url = (base_url or settings.cfbd_base_url).rstrip("/")

    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.api_key:
            raise RuntimeError("CFBD_API_KEY is not configured")
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last_exc: Exception | None = None
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=20.0) as client:
                    response = client.get(url, headers=headers, params=params)
                if response.status_code == 429:
                    last_exc = RuntimeError(f"CFBD rate limit on {path}")
                    retry_after = response.headers.get("Retry-After")
                    wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt)
                    time.sleep(min(max(wait_seconds, 1.0), 60.0))
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code == 429 and attempt < (max_attempts - 1):
                    time.sleep(min(2 ** attempt, 60))
                    continue
                raise
            except (httpx.ReadTimeout, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < (max_attempts - 1):
                    time.sleep(min(2 ** attempt, 30))
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("CFBD request failed unexpectedly")

    @staticmethod
    def _conference_param(conference: str | None) -> str | None:
        if not conference:
            return None
        normalized = conference.strip().upper().replace(" ", "")
        conference_map = {
            "BIG10": "B1G",
            "B1G": "B1G",
            "BIGTEN": "B1G",
            "BIG12": "B12",
            "B12": "B12",
            "SEC": "SEC",
            "ACC": "ACC",
        }
        return conference_map.get(normalized, conference.strip())

    def get_games_teams(
        self,
        season: int,
        week: int | None = None,
        season_type: str = "regular",
        conference: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"year": season, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        conference_param = self._conference_param(conference)
        if conference_param:
            params["conference"] = conference_param
        data = self._request("games/teams", params=params)
        if isinstance(data, list):
            return data
        return [data]

    def get_games(
        self,
        season: int,
        week: int | None = None,
        season_type: str = "regular",
        conference: str | None = None,
        team: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"year": season, "seasonType": season_type}
        if week is not None:
            params["week"] = week
        conference_param = self._conference_param(conference)
        if conference_param:
            params["conference"] = conference_param
        if team:
            params["team"] = team
        data = self._request("games", params=params)
        if isinstance(data, list):
            return data
        return [data]

    def get_season_stats(
        self,
        season: int,
        team: str | None = None,
        conference: str | None = None,
        start_week: int | None = None,
        end_week: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"year": season}
        if team:
            params["team"] = team
        conference_param = self._conference_param(conference)
        if conference_param:
            params["conference"] = conference_param
        if start_week is not None:
            params["startWeek"] = start_week
        if end_week is not None:
            params["endWeek"] = end_week
        data = self._request("stats/season", params=params)
        if isinstance(data, list):
            return data
        return [data]

    def get_season_advanced_stats(
        self,
        season: int,
        team: str | None = None,
        conference: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"year": season}
        if team:
            params["team"] = team
        conference_param = self._conference_param(conference)
        if conference_param:
            params["conference"] = conference_param
        data = self._request("stats/season/advanced", params=params)
        if isinstance(data, list):
            return data
        return [data]

    def get_records(
        self,
        season: int,
        conference: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"year": season}
        conference_param = self._conference_param(conference)
        if conference_param:
            params["conference"] = conference_param
        data = self._request("records", params=params)
        if isinstance(data, list):
            return data
        return [data]

    def get_game_advanced_box(self, game_id: int) -> dict[str, Any]:
        return self._request("game/box/advanced", params={"gameId": game_id})

    def get_wepa_team_season(
        self, season: int, conference: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"year": season}
        conference_param = self._conference_param(conference)
        if conference_param:
            params["conference"] = conference_param
        data = self._request("wepa/team/season", params=params)
        if isinstance(data, list):
            return data
        return [data]
