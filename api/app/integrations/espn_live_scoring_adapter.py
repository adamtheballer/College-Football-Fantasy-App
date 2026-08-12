"""Conservative ESPN college-football live-data adapter.

This module is the only layer allowed to know ESPN endpoint/JSON details.  It
returns provider-neutral payloads; it never scores players or writes a
database.  Callers must persist the raw response and resolve reviewed IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from collegefootballfantasy_api.app.domain.live_scoring_contract import (
    CANCELED,
    DELAYED,
    FINAL_UNVERIFIED,
    HALFTIME,
    IN_PROGRESS,
    POSTPONED,
    PRE_GAME,
    SCHEDULED,
    SUSPENDED,
)


class EspnLiveProviderError(RuntimeError):
    def __init__(self, *, category: str, message: str, status_code: int | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.category = category
        self.status_code = status_code
        self.retry_after = retry_after


@dataclass(frozen=True)
class EspnGame:
    game_id: str
    status: str
    season: int
    week: int
    start_at: datetime | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class EspnAthleteStatLine:
    athlete_id: str
    athlete_name: str | None
    team_id: str | None
    stats: dict[str, Any]
    completeness: str


@dataclass(frozen=True)
class EspnGameSummary:
    game: EspnGame
    athlete_lines: tuple[EspnAthleteStatLine, ...]
    payload: dict[str, Any]


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _status(event: dict[str, Any]) -> str:
    status = event.get("status") or {}
    kind = status.get("type") or {}
    state = str(kind.get("state") or "").lower()
    detail = " ".join(str(value or "") for value in (kind.get("name"), kind.get("description"), status.get("detail"))).lower()
    if "postpon" in detail:
        return POSTPONED
    if "cancel" in detail:
        return CANCELED
    if "suspend" in detail:
        return SUSPENDED
    if "delay" in detail:
        return DELAYED
    if state == "in":
        return HALFTIME if "half" in detail else IN_PROGRESS
    if state == "post" or bool(kind.get("completed")):
        return FINAL_UNVERIFIED
    return PRE_GAME if state == "pre" else SCHEDULED


def _value(stat: dict[str, Any]) -> str | None:
    value = stat.get("value")
    return str(value) if value is not None else None


def _put_if(source: dict[str, Any], result: dict[str, Any], *names: str) -> None:
    for name in names:
        if name in source and source[name] not in (None, ""):
            result[name] = source[name]
            return


def _made_attempted(value: Any) -> tuple[int | None, int | None]:
    """Parse ESPN's compact made/attempted stat (for example ``2/3``)."""
    if isinstance(value, str) and "/" in value:
        made, attempted = value.split("/", 1)
        try:
            return int(made), int(attempted)
        except ValueError:
            return None, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, None


def _stats_from_group(group_name: str, names: list[str], values: list[Any]) -> dict[str, Any]:
    raw = {str(name).strip().lower().replace(" ", "_"): values[index] for index, name in enumerate(names) if index < len(values)}
    output: dict[str, Any] = {}
    normalized_group = group_name.lower()
    if "passing" in normalized_group:
        _put_if(raw, output, "yds", "yards", "passing_yards")
        _put_if(raw, output, "td", "tds", "touchdowns")
        _put_if(raw, output, "int", "interceptions")
        completions, attempts = _made_attempted(raw.get("c/att", raw.get("comp/att")))
        output = {
            "pass_yards": output.get("yds", output.get("yards", output.get("passing_yards"))),
            "pass_tds": output.get("td", output.get("tds", output.get("touchdowns"))),
            "interceptions": output.get("int", output.get("interceptions")),
            "pass_completions": completions,
            "pass_attempts": attempts,
        }
    elif "rushing" in normalized_group:
        _put_if(raw, output, "yds", "yards", "rushing_yards")
        _put_if(raw, output, "td", "tds", "touchdowns")
        output = {
            "rush_yards": output.get("yds", output.get("yards", output.get("rushing_yards"))),
            "rush_tds": output.get("td", output.get("tds", output.get("touchdowns"))),
            "rush_attempts": raw.get("car", raw.get("attempts")),
        }
    elif "receiving" in normalized_group:
        _put_if(raw, output, "rec", "receptions")
        _put_if(raw, output, "yds", "yards", "receiving_yards")
        _put_if(raw, output, "td", "tds", "touchdowns")
        output = {"receptions": output.get("rec", output.get("receptions")), "rec_yards": output.get("yds", output.get("yards", output.get("receiving_yards"))), "rec_tds": output.get("td", output.get("tds", output.get("touchdowns")))}
    elif "kicking" in normalized_group:
        # ESPN's group endpoint supplies aggregate made attempts, but no
        # universally reliable distance buckets.  Preserve the data and mark
        # this line incomplete below rather than inventing a fantasy total.
        xp_made, _ = _made_attempted(raw.get("xp", raw.get("pat", raw.get("extra_points"))))
        fg_made, fg_attempted = _made_attempted(raw.get("fg", raw.get("field_goals")))
        output = {
            "xp_made": xp_made,
            "fg_made": fg_made,
            "fg_missed": (fg_attempted - fg_made) if fg_attempted is not None and fg_made is not None else None,
        }
    elif "fumble" in normalized_group:
        _put_if(raw, output, "lost", "fumbles_lost", "fum_lost")
        output = {"fumbles_lost": output.get("lost", output.get("fumbles_lost", output.get("fum_lost")))}
    return {key: value for key, value in output.items() if value is not None}


class EspnLiveScoringAdapter:
    provider = "espn"

    def __init__(self, *, base_url: str, timeout_seconds: int = 10, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = client

    def _request_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        close_client = self._client is None
        client = self._client or httpx.Client(timeout=self.timeout_seconds, headers={"User-Agent": "CollegeFootballFantasy/1.0 live-scoring"})
        try:
            response = client.get(f"{self.base_url}{path}", params=params)
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            if response.status_code == 429:
                raise EspnLiveProviderError(category="RATE_LIMITED", message="ESPN returned 429", status_code=429, retry_after=retry_seconds)
            if response.status_code == 403:
                raise EspnLiveProviderError(category="PROVIDER_BLOCKED", message="ESPN returned 403", status_code=403)
            if response.status_code >= 500:
                raise EspnLiveProviderError(category="PROVIDER_5XX", message=f"ESPN returned {response.status_code}", status_code=response.status_code)
            response.raise_for_status()
            try:
                payload = response.json()
            except (TypeError, ValueError) as exc:
                # A response that cannot be decoded is not an empty game.  It
                # is provider evidence that must leave the last verified
                # shadow score intact until a later complete revision arrives.
                raise EspnLiveProviderError(
                    category="INVALID_PAYLOAD",
                    message="ESPN response was not valid JSON",
                    status_code=response.status_code,
                ) from exc
            if not isinstance(payload, dict):
                raise EspnLiveProviderError(category="INVALID_PAYLOAD", message="ESPN response was not an object", status_code=response.status_code)
            return payload
        except httpx.TimeoutException as exc:
            raise EspnLiveProviderError(category="TIMEOUT", message="ESPN request timed out") from exc
        except httpx.HTTPError as exc:
            raise EspnLiveProviderError(category="NETWORK_ERROR", message="ESPN request failed") from exc
        finally:
            if close_client:
                client.close()

    def fetch_scoreboard(self, *, season: int, week: int) -> tuple[EspnGame, ...]:
        payload = self._request_json("/scoreboard", {"dates": season, "seasontype": 2, "week": week, "limit": 1000})
        games: list[EspnGame] = []
        for event in payload.get("events") or []:
            game_id = str(event.get("id") or "")
            if not game_id:
                continue
            games.append(EspnGame(game_id=game_id, status=_status(event), season=season, week=week, start_at=_parse_time(event.get("date")), payload=event))
        return tuple(games)

    def fetch_game_summary(self, *, game_id: str, season: int, week: int) -> EspnGameSummary:
        payload = self._request_json("/summary", {"event": game_id})
        header = payload.get("header") or {}
        competition = ((header.get("competitions") or [{}])[0])
        event = {"id": game_id, "date": competition.get("date"), "status": competition.get("status") or header.get("status") or {}}
        game = EspnGame(game_id=game_id, status=_status(event), season=season, week=week, start_at=_parse_time(event.get("date")), payload=event)
        # ESPN exposes passing, rushing, receiving, kicking, and fumbles in
        # separate category arrays.  Merge categories by the provider's
        # stable athlete ID before emitting a revision; otherwise a QB with
        # passing and rushing statistics would be scored from only the last
        # category received.
        athletes_by_id: dict[str, dict[str, Any]] = {}
        for team_group in ((payload.get("boxscore") or {}).get("players") or []):
            team = team_group.get("team") or {}
            team_id = str(team.get("id")) if team.get("id") is not None else None
            for category in team_group.get("statistics") or []:
                group_name = str(category.get("name") or category.get("displayName") or "")
                names = [str(name) for name in category.get("names") or []]
                for athlete_row in category.get("athletes") or []:
                    athlete = athlete_row.get("athlete") or {}
                    athlete_id = str(athlete.get("id") or "")
                    if not athlete_id:
                        continue
                    stats = _stats_from_group(group_name, names, list(athlete_row.get("stats") or []))
                    if not stats:
                        continue
                    aggregate = athletes_by_id.setdefault(
                        athlete_id,
                        {
                            "athlete_name": athlete.get("displayName") or athlete.get("shortName"),
                            "team_id": team_id,
                            "stats": {},
                            "has_kicking": False,
                        },
                    )
                    aggregate["stats"].update(stats)
                    aggregate["has_kicking"] = aggregate["has_kicking"] or "kicking" in group_name.lower()
        athletes = tuple(
            EspnAthleteStatLine(
                athlete_id=athlete_id,
                athlete_name=aggregate["athlete_name"],
                team_id=aggregate["team_id"],
                stats=aggregate["stats"],
                # Kicker scoring is incomplete until a verified distance
                # bucket source is available.  We store the raw aggregate but
                # never manufacture a fantasy-point total from it.
                completeness="incomplete" if aggregate["has_kicking"] else "complete",
            )
            for athlete_id, aggregate in athletes_by_id.items()
        )
        return EspnGameSummary(game=game, athlete_lines=athletes, payload=payload)
