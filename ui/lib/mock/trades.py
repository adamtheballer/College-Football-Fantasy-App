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


def generate_trades(league: dict, seed: str | None = None) -> dict:
    seed = seed or f"{league['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    teams = league["teams"]
    offers = []
    history = []

    for index in range(random.randint(2, 4)):
        team_a, team_b = random.sample(teams, 2)
        offers.append(
            {
                "id": index + 1,
                "from": team_a["name"],
                "to": team_b["name"],
                "give": [_make_player_name() for _ in range(random.randint(1, 2))],
                "receive": [_make_player_name() for _ in range(random.randint(1, 2))],
                "status": "Pending",
            }
        )

    for index in range(random.randint(3, 5)):
        team_a, team_b = random.sample(teams, 2)
        history.append(
            {
                "id": 100 + index,
                "from": team_a["name"],
                "to": team_b["name"],
                "give": [_make_player_name()],
                "receive": [_make_player_name()],
                "status": random.choice(["Accepted", "Rejected"]),
            }
        )

    return {"offers": offers, "history": history}
