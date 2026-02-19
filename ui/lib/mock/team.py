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


def _make_status() -> str:
    return random.choice(["Healthy", "Q", "D", "O"])


def _make_transaction(team_name: str) -> dict:
    action = random.choice(["Added", "Dropped", "Traded for", "Claimed"])
    player = _make_player_name()
    return {
        "action": action,
        "detail": f"{team_name} {action.lower()} {player}",
        "time": random.choice(["12m ago", "1h ago", "Yesterday", "2d ago", "3d ago"]),
    }


def _make_roster_slot(position: str, slot: str) -> dict:
    points = round(random.uniform(1.5, 26.5), 1)
    projection = round(points + random.uniform(-3.5, 5.5), 1)
    return {
        "name": _make_player_name(),
        "team": random.choice(
            ["Alabama", "Georgia", "Ohio State", "Oregon", "Texas", "LSU", "Michigan", "USC"]
        ),
        "pos": position,
        "slot": slot,
        "points": points,
        "proj": max(0.0, projection),
        "status": _make_status(),
    }


def generate_team_data(league: dict, team: dict, seed: str | None = None) -> dict:
    seed = seed or f"{league['id']}-{team['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    starters_slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DST"]
    bench_slots = ["QB", "RB", "WR", "TE", "RB"]
    ir_slots = ["IR"]

    starters = []
    for slot in starters_slots:
        actual_pos = random.choice(["RB", "WR", "TE"]) if slot == "FLEX" else slot
        starters.append(_make_roster_slot(actual_pos, slot))

    bench = []
    for slot in bench_slots:
        bench.append(_make_roster_slot(slot, "BENCH"))

    ir = []
    for _ in ir_slots:
        ir.append(_make_roster_slot(random.choice(["RB", "WR", "QB"]), "IR"))

    recent_weeks = []
    start_week = random.randint(4, 8)
    for offset in range(3):
        week = start_week + offset
        recent_weeks.append(
            {
                "week": week,
                "points": round(random.uniform(110, 185), 1),
            }
        )

    schedule = []
    for offset in range(1, 5):
        schedule.append(
            {
                "week": start_week + offset + 3,
                "opponent": random.choice([t["name"] for t in league["teams"] if t["id"] != team["id"]]),
                "projection": round(random.uniform(110, 175), 1),
            }
        )

    transactions = [_make_transaction(team["name"]) for _ in range(random.randint(4, 7))]

    start_sit = []
    if bench and starters:
        for _ in range(min(3, len(bench))):
            starter = random.choice(starters)
            bench_player = random.choice(bench)
            delta = round(bench_player["proj"] - starter["proj"], 1)
            if delta > 0:
                start_sit.append(
                    {
                        "start": bench_player["name"],
                        "sit": starter["name"],
                        "delta": delta,
                    }
                )

    return {
        "roster": {
            "starters": starters,
            "bench": bench,
            "ir": ir,
        },
        "recent_performance": recent_weeks,
        "schedule": schedule,
        "transactions": transactions,
        "start_sit": start_sit,
    }
