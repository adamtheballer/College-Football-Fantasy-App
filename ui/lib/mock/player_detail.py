from __future__ import annotations

import hashlib
import random
import time


def _hash_seed(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


def _make_status() -> str:
    return random.choice(["Final", "Q4", "Q3", "Q2", "Q1"])


def generate_player_detail(player: dict, seed: str | None = None) -> dict:
    seed = seed or f"{player['id']}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    game_log = []
    for week in range(1, 11):
        points = round(random.uniform(4.0, 28.0), 1)
        game_log.append(
            {
                "week": week,
                "opp": random.choice(
                    ["Alabama", "Georgia", "Ohio State", "Oregon", "Texas", "LSU", "Michigan", "USC"]
                ),
                "status": _make_status(),
                "points": points,
                "proj": round(points + random.uniform(-4.0, 6.0), 1),
            }
        )

    trend_points = [entry["points"] for entry in game_log[-6:]]

    news_blurbs = [
        "Dominated touches last week and saw a season-high workload.",
        "Coming off a tough matchup but projects to rebound.",
        "Coaches highlighted the red-zone usage this week.",
        "Expected to lead the offense in high-leverage snaps.",
        "Listed as probable after a limited practice report.",
    ]

    return {
        "player": player,
        "game_log": game_log,
        "trend_points": trend_points,
        "news": random.choice(news_blurbs),
    }
