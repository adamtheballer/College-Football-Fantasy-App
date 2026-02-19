from __future__ import annotations

import hashlib
import random


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
        "Ashton",
        "Tyler",
        "Donovan",
        "Jared",
        "Cade",
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
        "Henderson",
        "Benson",
        "Stark",
        "Cook",
        "Walker",
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def _power_four_teams() -> dict:
    return {
        "SEC": [
            "Alabama",
            "Georgia",
            "LSU",
            "Texas",
            "Florida",
            "Tennessee",
            "Auburn",
            "Ole Miss",
        ],
        "Big Ten": [
            "Ohio State",
            "Michigan",
            "Penn State",
            "Oregon",
            "USC",
            "Washington",
            "Wisconsin",
            "Iowa",
        ],
        "Big 12": [
            "Oklahoma State",
            "Kansas State",
            "Utah",
            "Arizona",
            "Iowa State",
            "TCU",
            "Baylor",
            "Texas Tech",
        ],
        "ACC": [
            "Florida State",
            "Clemson",
            "Miami",
            "NC State",
            "Louisville",
            "Virginia Tech",
            "Pitt",
            "SMU",
        ],
    }


def generate_players_data(seed: str, count: int = 240) -> dict:
    random.seed(_hash_seed(seed))

    teams_by_conf = _power_four_teams()
    team_pool = []
    for conf, teams in teams_by_conf.items():
        for team in teams:
            team_pool.append({"team": team, "conf": conf})

    positions = ["QB", "RB", "WR", "TE", "K"]
    weights = [0.12, 0.28, 0.36, 0.14, 0.1]
    class_years = ["Fr", "So", "Jr", "Sr"]

    players = []
    for index in range(count):
        team_info = random.choice(team_pool)
        position = random.choices(positions, weights=weights, k=1)[0]
        owned_pct = round(random.uniform(8, 96), 1)
        availability = "Owned" if owned_pct >= 55 else "FA"
        proj = round(random.uniform(4.0, 26.0), 1)
        last = round(max(0.0, proj + random.uniform(-6.0, 8.0)), 1)
        avg = round((proj + last) / 2 + random.uniform(-2.5, 2.5), 1)
        players.append(
            {
                "id": index + 1,
                "name": _make_player_name(),
                "pos": position,
                "team": team_info["team"],
                "school": team_info["team"],
                "class_year": random.choice(class_years),
                "conf": team_info["conf"],
                "availability": availability,
                "owned_pct": owned_pct,
                "proj": proj,
                "last": last,
                "avg": avg,
            }
        )

    teams = sorted({player["team"] for player in players})
    return {"seed": seed, "players": players, "teams": teams}
