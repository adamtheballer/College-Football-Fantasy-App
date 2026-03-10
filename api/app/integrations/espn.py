from __future__ import annotations

import json
import re
from typing import Any

import httpx


class ESPNClient:
    BASE_URL = "https://site.api.espn.com/apis/v2/sports/football/college-football"
    WEB_STANDINGS_URL = "https://www.espn.com/college-football/standings/_/group/{group}"
    CONFERENCE_GROUPS: dict[str, int] = {
        "ACC": 1,
        "BIG12": 4,
        "BIG10": 5,
        "SEC": 8,
    }

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        return {}

    def get_standings(self, season: int, conference: str) -> list[dict[str, Any]]:
        conference_key = conference.upper().replace(" ", "")
        group = self.CONFERENCE_GROUPS.get(conference_key)
        if not group:
            return []
        payload = self._request("standings", params={"group": group, "season": season})
        standings = payload.get("standings")
        if not isinstance(standings, dict):
            return []
        entries = standings.get("entries")
        if not isinstance(entries, list):
            return []
        return [row for row in entries if isinstance(row, dict)]

    def get_standings_from_page(self, season: int, conference: str) -> list[dict[str, Any]]:
        conference_key = conference.upper().replace(" ", "")
        group = self.CONFERENCE_GROUPS.get(conference_key)
        if not group:
            return []

        url = self.WEB_STANDINGS_URL.format(group=group)
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            response = client.get(url, params={"season": season})
        response.raise_for_status()
        html = response.text

        marker = "window['__espnfitt__']="  # embedded JSON payload in page source
        start = html.find(marker)
        if start < 0:
            return []
        start += len(marker)
        end = html.find(";</script>", start)
        if end < 0:
            return []

        try:
            payload = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []

        standings_root = (
            payload.get("page", {})
            .get("content", {})
            .get("standings", {})
            .get("groups", {})
        )
        if not isinstance(standings_root, dict):
            return []

        headers = standings_root.get("headers")
        groups = standings_root.get("groups")
        if not isinstance(headers, dict) or not isinstance(groups, list) or not groups:
            return []

        first_group = groups[0]
        if not isinstance(first_group, dict):
            return []
        rows = first_group.get("standings")
        if not isinstance(rows, list):
            return []

        # ESPN exposes index mapping in headers metadata (e.g. vsconf -> 59, total -> 11, playoffseed -> 2).
        rank_idx = int(headers.get("playoffseed", {}).get("i", 2))
        conf_idx = int(headers.get("vsconf", {}).get("i", 59))
        overall_idx = int(headers.get("total", {}).get("i", 11))

        parsed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            team_payload = row.get("team")
            stats = row.get("stats")
            if not isinstance(team_payload, dict) or not isinstance(stats, list):
                continue
            if max(rank_idx, conf_idx, overall_idx) >= len(stats):
                continue

            team_name = (
                team_payload.get("location")
                or team_payload.get("shortDisplayName")
                or team_payload.get("displayName")
                or team_payload.get("name")
            )
            if not team_name:
                continue

            rank_raw = str(stats[rank_idx]).strip()
            conf_summary = str(stats[conf_idx]).strip()
            overall_summary = str(stats[overall_idx]).strip()
            if not conf_summary or conf_summary == "-":
                continue
            if not overall_summary or overall_summary == "-":
                continue

            rank = None
            try:
                rank = int(float(rank_raw))
            except ValueError:
                rank = None

            parsed.append(
                {
                    "team": str(team_name).strip(),
                    "rank": rank,
                    "conference_record": conf_summary,
                    "overall_record": overall_summary,
                }
            )

        # If rank is missing for some rows, keep stable order from page (already in standings order).
        # Otherwise order by displayed rank from ESPN page.
        if parsed and all(isinstance(row.get("rank"), int) for row in parsed):
            parsed.sort(key=lambda row: int(row["rank"]))
        return parsed
