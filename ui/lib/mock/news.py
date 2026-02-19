from __future__ import annotations

import hashlib
import random
import time


def _hash_seed(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


def generate_league_news(league: dict, seed: str | None = None) -> dict:
    seed = seed or f"{league['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    teams = [team["name"] for team in league["teams"]]
    headlines = [
        "Statement win shakes up the standings",
        "Injury shakeup forces lineup pivots",
        "Breakout performance swings the matchup",
        "Playoff push heats up in rivalry week",
        "Defense delivers a surprise upset",
        "Freshman star emerges in the fourth quarter",
    ]
    previews = []
    for _ in range(3):
        away, home = random.sample(teams, 2)
        previews.append(
            {
                "title": f"{away} at {home}",
                "summary": f"{away} leans on its backfield while {home} enters with momentum.",
            }
        )

    positions = ["QB", "RB", "WR", "TE", "K"]
    injuries = []
    for _ in range(5):
        team = random.choice(teams)
        injuries.append(
            {
                "player": random.choice(
                    [
                        "Jalen Daniels",
                        "Caleb Williams",
                        "Marvin Harrison",
                        "Xavier Worthy",
                        "Trevor Etienne",
                        "Brock Bowers",
                    ]
                ),
                "team": team,
                "pos": random.choice(positions),
                "status": random.choice(["Questionable", "Doubtful", "Out", "Probable"]),
                "impact": random.choice(["High", "Medium", "Low"]),
            }
        )

    return {
        "headlines": [
            {
                "title": random.choice(headlines),
                "summary": f"{random.choice(teams)} climbs the ranks after a dominant showing.",
                "time": random.choice(["30m ago", "2h ago", "Yesterday"]),
            }
            for _ in range(4)
        ],
        "previews": previews,
        "injuries": injuries,
    }
