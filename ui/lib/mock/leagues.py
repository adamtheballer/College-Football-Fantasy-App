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


def _make_record() -> tuple[int, int]:
    wins = random.randint(2, 8)
    losses = random.randint(0, 5)
    if wins == losses:
        losses = max(0, losses - 1)
    return wins, losses


def generate_leagues_data(seed: str | None = None) -> dict:
    seed = seed or str(time.time_ns())
    random.seed(_hash_seed(seed))

    leagues = []
    league_count = random.randint(3, 8)
    league_ids = random.sample(range(1001, 9999), league_count)

    for league_id in league_ids:
        team_count = random.choice([8, 10, 12])
        teams = []
        for _ in range(team_count):
            wins, losses = _make_record()
            teams.append(
                {
                    "name": _make_team_name(),
                    "wins": wins,
                    "losses": losses,
                }
            )

        teams_sorted = sorted(teams, key=lambda item: (item["wins"], -item["losses"]), reverse=True)
        standings_preview = []
        for idx, team in enumerate(teams_sorted[:3], start=1):
            standings_preview.append(
                {
                    "rank": idx,
                    "team": team["name"],
                    "record": f"{team['wins']}-{team['losses']}",
                }
            )

        leagues.append(
            {
                "id": league_id,
                "name": _make_league_name(),
                "current_week": random.randint(5, 12),
                "team_count": team_count,
                "standings_preview": standings_preview,
            }
        )

    return {"seed": seed, "leagues": leagues}
