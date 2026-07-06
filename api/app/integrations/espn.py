from __future__ import annotations

import json
import re
from typing import Any

import httpx


class ESPNClient:
    BASE_URL = "https://site.api.espn.com/apis/v2/sports/football/college-football"
    SITE_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
    WEB_BASE_URL = "https://site.web.api.espn.com/apis/common/v3/sports/football/college-football"
    WEB_STANDINGS_URL = "https://www.espn.com/college-football/standings/_/group/{group}"
    FBS_GROUP = 80
    CONFERENCE_GROUPS: dict[str, int] = {
        "ACC": 1,
        "BIG12": 4,
        "BIG10": 5,
        "SEC": 8,
    }

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    def _request(self, path: str, params: dict[str, Any], *, base_url: str | None = None) -> dict[str, Any]:
        url = f"{(base_url or self.base_url).rstrip('/')}/{path.lstrip('/')}"
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        return {}

    def get_scoreboard_events(
        self,
        season: int,
        week: int,
        *,
        seasontype: int = 2,
        group: int = FBS_GROUP,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "scoreboard",
            params={
                "dates": season,
                "seasontype": seasontype,
                "week": week,
                "groups": group,
                "limit": limit,
            },
            base_url=self.SITE_BASE_URL,
        )
        events = payload.get("events")
        if not isinstance(events, list):
            return []
        return [event for event in events if isinstance(event, dict)]

    def get_summary(self, event_id: str | int) -> dict[str, Any]:
        return self._request("summary", params={"event": event_id}, base_url=self.SITE_BASE_URL)

    def get_athlete_profile(self, espn_player_id: str | int) -> dict[str, Any]:
        return self._request(f"athletes/{espn_player_id}", params={}, base_url=self.WEB_BASE_URL)

    def get_weekly_boxscore_summaries(self, season: int, week: int, *, seasontype: int = 2) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for event in self.get_scoreboard_events(season=season, week=week, seasontype=seasontype):
            event_id = event.get("id")
            if event_id is None:
                continue
            summary = self.get_summary(event_id)
            if summary:
                summary.setdefault("event_id", str(event_id))
                summaries.append(summary)
        return summaries

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


ESPN_STAT_KEY_MAP = {
    "passingYards": "pass_yards",
    "passingTouchdowns": "pass_tds",
    "interceptions": "interceptions",
    "rushingYards": "rush_yards",
    "rushingTouchdowns": "rush_tds",
    "receptions": "receptions",
    "receivingYards": "rec_yards",
    "receivingTouchdowns": "rec_tds",
    "fumblesLost": "fumbles_lost",
}


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text or text == "--":
        return 0.0
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def _made(value: Any) -> float:
    text = str(value or "").strip()
    if not text or text == "--":
        return 0.0
    if "/" in text:
        text = text.split("/", 1)[0]
    if "-" in text:
        text = text.split("-", 1)[0]
    return _number(text)


def _team_aliases(team: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for key in ("location", "shortDisplayName", "displayName", "name", "abbreviation"):
        value = team.get(key)
        if value:
            aliases.append(str(value).strip())
    return list(dict.fromkeys(aliases))


def _field_goal_bucket(distance: int) -> str:
    if distance >= 50:
        return "fg_made_50_plus"
    if distance >= 40:
        return "fg_made_40_49"
    return "fg_made_0_39"


def _field_goal_buckets_from_scoring_plays(summary: dict[str, Any]) -> dict[str, dict[str, int]]:
    buckets: dict[str, dict[str, int]] = {}
    drives = summary.get("drives")
    if not isinstance(drives, dict):
        return buckets
    previous = drives.get("previous")
    if not isinstance(previous, list):
        return buckets
    for drive in previous:
        if not isinstance(drive, dict):
            continue
        plays = drive.get("plays")
        if not isinstance(plays, list):
            continue
        for play in plays:
            if not isinstance(play, dict) or not play.get("scoringPlay"):
                continue
            text = str(play.get("text") or "")
            if "Field Goal" not in text:
                continue
            distance_match = re.search(r"(\d+)\s+Yd Field Goal", text, re.IGNORECASE)
            if not distance_match:
                continue
            distance = int(distance_match.group(1))
            name = text[: distance_match.start()].strip(" ,-")
            if not name:
                continue
            bucket = _field_goal_bucket(distance)
            row = buckets.setdefault(name.lower(), {"fg_made_0_39": 0, "fg_made_40_49": 0, "fg_made_50_plus": 0})
            row[bucket] += 1
    return buckets


def extract_player_box_score_stats(summary: dict[str, Any]) -> list[dict[str, Any]]:
    event_id = str(summary.get("event_id") or summary.get("header", {}).get("id") or "")
    field_goal_buckets = _field_goal_buckets_from_scoring_plays(summary)
    rows_by_athlete: dict[str, dict[str, Any]] = {}
    boxscore = summary.get("boxscore")
    players_by_team = boxscore.get("players") if isinstance(boxscore, dict) else None
    if not isinstance(players_by_team, list):
        return []

    for team_payload in players_by_team:
        if not isinstance(team_payload, dict):
            continue
        team = team_payload.get("team")
        if not isinstance(team, dict):
            team = {}
        team_aliases = _team_aliases(team)
        statistics = team_payload.get("statistics")
        if not isinstance(statistics, list):
            continue

        for category in statistics:
            if not isinstance(category, dict):
                continue
            keys = category.get("keys")
            athletes = category.get("athletes")
            if not isinstance(keys, list) or not isinstance(athletes, list):
                continue

            for athlete_row in athletes:
                if not isinstance(athlete_row, dict):
                    continue
                athlete = athlete_row.get("athlete")
                stats = athlete_row.get("stats")
                if not isinstance(athlete, dict) or not isinstance(stats, list):
                    continue
                espn_player_id = str(athlete.get("id") or "")
                player_name = str(athlete.get("displayName") or "").strip()
                if not espn_player_id or not player_name or player_name.lower() == "team":
                    continue
                row = rows_by_athlete.setdefault(
                    espn_player_id,
                    {
                        "provider": "espn",
                        "EventID": event_id,
                        "ESPNPlayerID": espn_player_id,
                        "PlayerName": player_name,
                        "Team": team.get("displayName"),
                        "School": team.get("location") or team.get("shortDisplayName"),
                        "TeamAliases": team_aliases,
                    },
                )
                for key, stat_value in zip(keys, stats, strict=False):
                    canonical = ESPN_STAT_KEY_MAP.get(str(key))
                    if canonical:
                        row[canonical] = row.get(canonical, 0.0) + _number(stat_value)
                    elif key == "extraPointsMade/extraPointAttempts":
                        row["xp_made"] = row.get("xp_made", 0.0) + _made(stat_value)
                    elif key == "fieldGoalsMade/fieldGoalAttempts":
                        row["espn_field_goals_made_unbucketed"] = row.get("espn_field_goals_made_unbucketed", 0.0) + _made(stat_value)

    for row in rows_by_athlete.values():
        player_name = str(row.get("PlayerName") or "").lower()
        buckets = field_goal_buckets.get(player_name)
        if not buckets:
            continue
        for key, value in buckets.items():
            row[key] = row.get(key, 0.0) + value
        row["espn_field_goal_distance_detail_available"] = True

    return list(rows_by_athlete.values())
