from __future__ import annotations

import hashlib

from ui.lib.mock.league import generate_league_data
from ui.lib.mock.players import generate_players_data
from ui.lib.mock.schedule import generate_schedule


def public_id_for_league(league_id: int) -> str:
    return hashlib.sha256(str(league_id).encode("utf-8")).hexdigest()[:8]


def _mask_name(name: str) -> str:
    parts = name.split()
    masked_parts = []
    for part in parts:
        if len(part) <= 2:
            masked_parts.append(part[0] + "*")
        else:
            masked_parts.append(part[:2] + "***")
    return " ".join(masked_parts)


def generate_public_league(public_id: str) -> dict:
    league_id = int(public_id, 16) % 9000 + 1000
    league_data = generate_league_data(league_id, seed=public_id)["league"]
    league_data["name"] = _mask_name(league_data["name"])
    for team in league_data["teams"]:
        team["name"] = _mask_name(team["name"])
        team["owner"] = "Hidden"

    standings = sorted(league_data["teams"], key=lambda item: item["wins"], reverse=True)

    schedule = generate_schedule(league_data, seed=public_id, weeks=4)["weeks"]

    players = generate_players_data(public_id, count=80)["players"]
    top_performers = sorted(players, key=lambda item: item["proj"], reverse=True)[:5]

    return {
        "public_id": public_id,
        "league": league_data,
        "standings": standings,
        "schedule": schedule,
        "top_performers": top_performers,
    }
