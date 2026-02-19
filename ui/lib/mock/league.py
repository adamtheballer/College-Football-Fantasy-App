from __future__ import annotations

import hashlib
import random
import time


def _hash_seed(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


def _make_league_name() -> str:
    starts = [
        "Saturday",
        "Campus",
        "Rivalry",
        "Gridiron",
        "Bowl",
        "Tailgate",
        "Heisman",
        "Playoff",
    ]
    ends = [
        "Showdown",
        "Clash",
        "Legends",
        "League",
        "Circuit",
        "Cup",
        "Series",
        "Alliance",
    ]
    return f"{random.choice(starts)} {random.choice(ends)}"


def _make_team_name() -> str:
    adjectives = [
        "Iron",
        "Crimson",
        "Golden",
        "Midnight",
        "Coastal",
        "River",
        "Mountain",
        "Emerald",
        "Lone",
        "Capital",
        "Prairie",
        "Bay",
        "Royal",
        "Storm",
        "Steel",
    ]
    mascots = [
        "Hawks",
        "Tigers",
        "Knights",
        "Bears",
        "Wolves",
        "Rams",
        "Spartans",
        "Raiders",
        "Falcons",
        "Cyclones",
        "Pirates",
        "Bruins",
        "Warriors",
        "Eagles",
        "Gators",
    ]
    return f"{random.choice(adjectives)} {random.choice(mascots)}"


def generate_league_data(league_id: int, seed: str | None = None) -> dict:
    seed = seed or f"{league_id}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    team_count = random.choice([8, 10, 12])
    teams = []
    for index in range(team_count):
        wins = random.randint(2, 8)
        losses = random.randint(0, 6)
        ties = random.randint(0, 1) if random.random() < 0.12 else 0
        points_for = round(random.uniform(820, 1320), 1)
        points_against = round(points_for - random.uniform(-120, 160), 1)
        streak_value = random.randint(1, 4)
        streak_type = random.choice(["W", "L"])
        teams.append(
            {
                "id": index + 1,
                "name": _make_team_name(),
                "owner": f"Owner {index + 1}",
                "record": f"{wins}-{losses}",
                "points_for": points_for,
                "points_against": points_against,
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "streak": f"{streak_type}{streak_value}",
                "roster_summary": {
                    "starters": 9,
                    "bench": random.randint(4, 6),
                    "ir": random.randint(0, 2),
                },
            }
        )

    draft_status = random.choice(["off", "scheduled", "live", "complete"])
    draft_rounds = random.choice([10, 12, 15])

    user_team_id = random.choice(teams)["id"] if teams else None
    return {
        "seed": seed,
        "league": {
            "id": league_id,
            "name": _make_league_name(),
            "commissioner": random.choice([True, False]),
            "current_week": random.randint(5, 12),
            "teams": teams,
            "user_team_id": user_team_id,
            "draft": {
                "status": draft_status,
                "rounds": draft_rounds,
            },
        },
    }
