from __future__ import annotations

import hashlib
import random
import time


def _hash_seed(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


def _make_player_name() -> str:
    first_names = [
        "Jalen",
        "Caleb",
        "Drake",
        "Bo",
        "Marvin",
        "Rome",
        "Xavier",
        "Malik",
        "Trevor",
        "Quinn",
        "Jordan",
        "Brock",
        "JJ",
        "Evan",
        "Cam",
    ]
    last_names = [
        "Daniels",
        "Williams",
        "Maye",
        "Nix",
        "Harrison",
        "Odunze",
        "Worthy",
        "Nabers",
        "Etienne",
        "Ewers",
        "Travis",
        "Bowers",
        "McCarthy",
        "Stewart",
        "Ward",
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def generate_waivers(league: dict, seed: str | None = None) -> dict:
    seed = seed or f"{league['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    teams = league["teams"]
    budgets = []
    for team in teams:
        budgets.append(
            {
                "team": team["name"],
                "faab": random.randint(20, 100),
                "priority": random.randint(1, len(teams)),
            }
        )

    budgets_sorted = sorted(budgets, key=lambda item: item["priority"])
    claims = []
    for order in range(1, random.randint(6, 12)):
        team = random.choice(teams)
        claims.append(
            {
                "order": order,
                "team": team["name"],
                "add": _make_player_name(),
                "drop": _make_player_name(),
                "status": random.choice(["Pending", "Processing"]),
            }
        )

    return {"budgets": budgets, "priority": budgets_sorted, "claims": claims}
