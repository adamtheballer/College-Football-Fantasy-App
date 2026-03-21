#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import httpx
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from collegefootballfantasy_api.app.models import (  # noqa: F401
    draft,
    league,
    league_invite,
    league_member,
    league_settings,
    player,
    player_stat,
    roster,
    scheduled_notification,
    team,
    user,
)
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat

DEFAULT_SEED_PATH = PROJECT_ROOT / "data" / "seeds" / "college_football_fantasy_seed.json"


def extract_json_section(markdown: str, heading: str) -> list[dict]:
    pattern = rf"^## {re.escape(heading)}\s*```json\s*(.*?)\s*```"
    match = re.search(pattern, markdown, re.MULTILINE | re.DOTALL)
    if not match:
        raise ValueError(f"Could not find JSON section for heading: {heading}")
    return json.loads(match.group(1))


def normalize_lookup(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9]+", "", normalized.lower())
    return normalized


def extract_roster_urls(markdown: str) -> list[str]:
    urls: list[str] = []
    for line in markdown.splitlines():
        if "Roster 2026" not in line or "espn.com" not in line:
            continue
        match = re.search(r"https?://\S+", line)
        if match:
            urls.append(match.group(0))
    return urls


def extract_json_array(source: str, start_token: str) -> list[dict]:
    token_index = source.find(start_token)
    if token_index == -1:
        raise ValueError(f"Could not find token: {start_token}")

    start_index = source.find("[", token_index)
    if start_index == -1:
        raise ValueError(f"Could not find array start for token: {start_token}")
    depth = 0
    in_string = False
    escaped = False

    for index in range(start_index, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return json.loads(source[start_index : index + 1])

    raise ValueError(f"Could not parse JSON array for token: {start_token}")


def build_headshot_index(urls: list[str]) -> dict[tuple[str, str, str], str]:
    client = httpx.Client(
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    headshots: dict[tuple[str, str, str], str] = {}

    try:
        for url in urls:
            html = client.get(url).text
            groups = extract_json_array(html, '"groups":[{"name":"Offense"')
            for group in groups:
                for athlete in group.get("athletes", []):
                    school = athlete.get("college")
                    name = athlete.get("name")
                    position = athlete.get("position")
                    headshot = athlete.get("headshot")
                    if not school or not name or not position or not headshot:
                        continue
                    key = (
                        normalize_lookup(name),
                        normalize_lookup(school),
                        normalize_lookup(position),
                    )
                    headshots[key] = headshot
    finally:
        client.close()

    return headshots


def load_seed_payload(path: Path) -> tuple[list[dict], list[dict], list[str]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return (
            payload.get("players", []),
            payload.get("player_stats", []),
            payload.get("roster_source_urls", []),
        )

    markdown = path.read_text(encoding="utf-8")
    return (
        extract_json_section(markdown, "players_json"),
        extract_json_section(markdown, "player_stats_json"),
        extract_roster_urls(markdown),
    )


def import_seed_file(path: Path) -> tuple[int, int, int, int, int]:
    players_payload, player_stats_payload, roster_urls = load_seed_payload(path)
    headshot_index = build_headshot_index(roster_urls)

    created_players = 0
    updated_players = 0
    created_stats = 0
    updated_stats = 0
    updated_images = 0

    with SessionLocal() as session:
        player_index: dict[tuple[str, str, str], Player] = {
            (player.name, player.school, player.position): player
            for player in session.scalars(select(Player)).all()
        }

        for payload in players_payload:
            key = (payload["name"], payload["school"], payload["position"])
            player = player_index.get(key)
            if player is None:
                player = Player(
                    external_id=payload.get("external_id"),
                    name=payload["name"],
                    position=payload["position"],
                    school=payload["school"],
                    image_url=payload.get("image_url")
                    or headshot_index.get(
                        (
                            normalize_lookup(payload["name"]),
                            normalize_lookup(payload["school"]),
                            normalize_lookup(payload["position"]),
                        )
                    ),
                )
                session.add(player)
                session.flush()
                player_index[key] = player
                created_players += 1
            else:
                next_external_id = payload.get("external_id")
                if player.external_id != next_external_id:
                    player.external_id = next_external_id
                    updated_players += 1
                next_image_url = payload.get("image_url") or headshot_index.get(
                    (
                        normalize_lookup(payload["name"]),
                        normalize_lookup(payload["school"]),
                        normalize_lookup(payload["position"]),
                    )
                )
                if next_image_url and player.image_url != next_image_url:
                    player.image_url = next_image_url
                    updated_images += 1

        for payload in player_stats_payload:
            lookup = payload["player_lookup"]
            key = (lookup["name"], lookup["school"], lookup["position"])
            player = player_index.get(key)
            if player is None:
                raise ValueError(f"Missing player for stats row: {key}")

            stat = session.scalar(
                select(PlayerStat).where(
                    PlayerStat.player_id == player.id,
                    PlayerStat.season == payload["season"],
                    PlayerStat.week == payload["week"],
                )
            )

            if stat is None:
                stat = PlayerStat(
                    player_id=player.id,
                    season=payload["season"],
                    week=payload["week"],
                    source=payload.get("source", "seed_research"),
                    stats=payload["stats"],
                )
                session.add(stat)
                created_stats += 1
            else:
                changed = False
                next_source = payload.get("source", "seed_research")
                if stat.source != next_source:
                    stat.source = next_source
                    changed = True
                if stat.stats != payload["stats"]:
                    stat.stats = payload["stats"]
                    changed = True
                if changed:
                    updated_stats += 1

        session.commit()

    return created_players, updated_players, created_stats, updated_stats, updated_images


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import player seed research into players and player_stats."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help=f"Path to the seed JSON or markdown file (default: {DEFAULT_SEED_PATH})",
    )
    args = parser.parse_args()

    created_players, updated_players, created_stats, updated_stats, updated_images = import_seed_file(args.path)
    print(
        "Imported seed research: "
        f"players created={created_players}, "
        f"players updated={updated_players}, "
        f"stats created={created_stats}, "
        f"stats updated={updated_stats}, "
        f"images updated={updated_images}"
    )


if __name__ == "__main__":
    main()
