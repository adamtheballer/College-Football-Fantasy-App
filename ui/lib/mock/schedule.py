from __future__ import annotations

import hashlib
import random
import time


def _hash_seed(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


def _rotate(teams: list[dict]) -> list[dict]:
    if len(teams) <= 2:
        return teams
    fixed = teams[0]
    rest = teams[1:]
    rest = [rest[-1]] + rest[:-1]
    return [fixed] + rest


def generate_schedule(league: dict, seed: str | None = None, weeks: int = 15) -> dict:
    seed = seed or f"{league['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    teams = list(league["teams"])
    if len(teams) % 2 != 0:
        teams.append({"id": -1, "name": "BYE"})

    order = teams[:]
    schedule = {}

    for week in range(1, weeks + 1):
        matchups = []
        for index in range(len(order) // 2):
            home = order[index]
            away = order[-(index + 1)]
            if home["id"] == -1 or away["id"] == -1:
                continue
            if random.random() > 0.5:
                home, away = away, home
            home_score = round(random.uniform(82, 168), 1)
            away_score = round(random.uniform(82, 168), 1)
            matchups.append(
                {
                    "home": home["name"],
                    "away": away["name"],
                    "home_score": home_score,
                    "away_score": away_score,
                    "home_proj": round(home_score + random.uniform(-10, 12), 1),
                    "away_proj": round(away_score + random.uniform(-10, 12), 1),
                    "winner": "home" if home_score >= away_score else "away",
                }
            )
        schedule[week] = matchups
        order = _rotate(order)

    return {"seed": seed, "weeks": schedule}
