from __future__ import annotations

import hashlib
import random
import time
from datetime import datetime, timedelta

from ui.lib.team_branding import team_color


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


def _format_relative_time(now: datetime, timestamp: datetime) -> str:
    delta = now - timestamp
    minutes = int(delta.total_seconds() / 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days == 1:
        return "Yesterday"
    return f"{days}d ago"


def _team_badge(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return name[:2].upper()


def generate_transactions(league: dict, seed: str | None = None) -> list[dict]:
    seed = seed or f"{league['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    teams = league["teams"]
    now = datetime.now()
    count = random.randint(20, 50)
    transactions = []

    for _ in range(count):
        team = random.choice(teams)
        transaction_type = random.choice(["Add", "Drop", "Trade", "Claim"])
        player = _make_player_name()
        other_team = random.choice([t for t in teams if t["id"] != team["id"]])
        minutes_ago = random.randint(10, 60 * 24 * 10)
        timestamp = now - timedelta(minutes=minutes_ago)

        detail = ""
        faab = None
        priority = None

        if transaction_type == "Add":
            detail = f"{team['name']} added {player}"
        elif transaction_type == "Drop":
            detail = f"{team['name']} dropped {player}"
        elif transaction_type == "Trade":
            detail = f"{team['name']} traded {player} to {other_team['name']}"
        else:
            detail = f"{team['name']} claimed {player}"
            if random.random() > 0.4:
                faab = random.randint(1, 25)
            priority = random.randint(1, len(teams))

        transactions.append(
            {
                "team": team["name"],
                "team_badge": _team_badge(team["name"]),
                "team_color": team_color(team["name"]),
                "type": transaction_type,
                "detail": detail,
                "timestamp": timestamp,
                "time_label": "",
                "faab": faab,
                "priority": priority,
            }
        )

    transactions.sort(key=lambda item: item["timestamp"], reverse=True)
    for item in transactions:
        item["time_label"] = _format_relative_time(now, item["timestamp"])
    return transactions
