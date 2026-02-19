from __future__ import annotations

import hashlib
import random
import time

from ui.lib.mock.players import generate_players_data


def _hash_seed(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


def generate_draft_state(league: dict, seed: str | None = None) -> dict:
    seed = seed or f"{league['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    rounds = league.get("draft", {}).get("rounds", 12)
    order = random.sample(league["teams"], k=len(league["teams"]))
    order = [{"id": team["id"], "name": team["name"]} for team in order]

    players_data = generate_players_data(seed, count=220)
    available_players = sorted(players_data["players"], key=lambda item: item["proj"], reverse=True)

    return {
        "rounds": rounds,
        "order": order,
        "available": available_players,
        "picks": [],
    }
