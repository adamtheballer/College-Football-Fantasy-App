import os
from typing import Any
from urllib.parse import urlencode

import httpx
import streamlit as st

BASE_URL = os.getenv("UI_API_BASE_URL", "http://localhost:8000")
TIMEOUT = 10.0


def _request(method: str, path: str, payload: dict | list | None = None) -> Any:
    url = f"{BASE_URL}{path}"
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.request(method, url, json=payload)
    response.raise_for_status()
    if response.status_code == 204:
        return None
    return response.json()


@st.cache_data(show_spinner=False)
def get_leagues() -> dict:
    return _request("GET", "/leagues")


def create_league(payload: dict) -> dict:
    data = _request("POST", "/leagues", payload)
    st.cache_data.clear()
    return data


def update_league(league_id: int, payload: dict) -> dict:
    data = _request("PUT", f"/leagues/{league_id}", payload)
    st.cache_data.clear()
    return data


def delete_league(league_id: int) -> None:
    _request("DELETE", f"/leagues/{league_id}")
    st.cache_data.clear()


@st.cache_data(show_spinner=False)
def get_teams(league_id: int) -> dict:
    return _request("GET", f"/leagues/{league_id}/teams")


def create_team(league_id: int, payload: dict) -> dict:
    data = _request("POST", f"/leagues/{league_id}/teams", payload)
    st.cache_data.clear()
    return data


@st.cache_data(show_spinner=False)
def get_players(filters: dict | None = None) -> dict:
    path = "/players"
    if filters:
        query = urlencode({key: value for key, value in filters.items() if value})
        if query:
            path = f"{path}?{query}"
    return _request("GET", path)


def create_players(payload: list[dict]) -> list[dict]:
    data = _request("POST", "/players", payload)
    st.cache_data.clear()
    return data


def get_player_stats(player_id: int, season: int | None = None, week: int | None = None, refresh: bool = False) -> dict:
    params = {}
    if season is not None:
        params["season"] = season
    if week is not None:
        params["week"] = week
    if refresh:
        params["refresh"] = "true"
    query = urlencode(params)
    path = f"/players/{player_id}/stats"
    if query:
        path = f"{path}?{query}"
    return _request("GET", path)


@st.cache_data(show_spinner=False)
def get_roster(team_id: int) -> dict:
    return _request("GET", f"/teams/{team_id}/roster")


def add_roster_entry(team_id: int, payload: dict) -> dict:
    data = _request("POST", f"/teams/{team_id}/roster", payload)
    st.cache_data.clear()
    return data


def delete_roster_entry(team_id: int, roster_entry_id: int) -> None:
    _request("DELETE", f"/teams/{team_id}/roster/{roster_entry_id}")
    st.cache_data.clear()
