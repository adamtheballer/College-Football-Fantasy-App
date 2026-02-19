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
    statuses = [
        "Final",
        "Q4 2:31",
        "Q3 8:12",
        "Q2 1:44",
        "Q1 9:55",
        "Halftime",
    ]
    return random.choice(statuses)


def _make_stats(position: str) -> tuple[str, dict]:
    if position == "QB":
        comp = random.randint(18, 28)
        att = random.randint(28, 40)
        yards = random.randint(210, 380)
        tds = random.randint(1, 4)
        return (
            f"Pass {comp}/{att}, {yards} YDS, {tds} TD",
            {"Comp": comp, "Att": att, "Pass Yds": yards, "Pass TD": tds},
        )
    if position == "RB":
        carries = random.randint(10, 24)
        yards = random.randint(45, 160)
        tds = random.randint(0, 3)
        return (
            f"{carries} CAR, {yards} YDS, {tds} TD",
            {"Car": carries, "Rush Yds": yards, "Rush TD": tds},
        )
    if position in {"WR", "TE"}:
        rec = random.randint(4, 10)
        yards = random.randint(45, 145)
        tds = random.randint(0, 2)
        return (
            f"{rec} REC, {yards} YDS, {tds} TD",
            {"Rec": rec, "Rec Yds": yards, "Rec TD": tds},
        )
    if position == "K":
        fg_made = random.randint(1, 3)
        fg_att = random.randint(fg_made, 3)
        xp_made = random.randint(1, 4)
        xp_att = random.randint(xp_made, 4)
        return (
            f"FG {fg_made}/{fg_att}, XP {xp_made}/{xp_att}",
            {"FG": fg_made, "FGA": fg_att, "XP": xp_made, "XPA": xp_att},
        )
    if position == "DST":
        sacks = random.randint(1, 4)
        ints = random.randint(0, 2)
        return (f"{sacks} SACK, {ints} INT", {"Sack": sacks, "INT": ints})
    return ("Team impact play", {"Plays": random.randint(2, 6)})


def _make_player(position: str) -> dict:
    points = round(random.uniform(2.5, 28.5), 1)
    projection = round(points + random.uniform(-4.0, 6.0), 1)
    stat_line, stat_breakdown = _make_stats(position)
    return {
        "name": _make_player_name(),
        "team": random.choice(
            [
                "Alabama",
                "Georgia",
                "Ohio State",
                "Oregon",
                "Texas",
                "LSU",
                "Michigan",
                "USC",
            ]
        ),
        "pos": position,
        "points": points,
        "proj": max(0.0, projection),
        "status": _make_status(),
        "stats": stat_line,
        "stat_breakdown": stat_breakdown,
    }


def _build_lineup() -> dict:
    starters_slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DST"]
    bench_slots = ["QB", "RB", "WR", "TE", "RB"]

    starters = []
    for slot in starters_slots:
        actual_pos = random.choice(["RB", "WR", "TE"]) if slot == "FLEX" else slot
        player = _make_player(actual_pos)
        player["slot"] = slot
        starters.append(player)

    bench = []
    for slot in bench_slots:
        player = _make_player(slot)
        player["slot"] = "BENCH"
        bench.append(player)

    total_points = round(sum(player["points"] for player in starters), 1)
    total_proj = round(sum(player["proj"] for player in starters), 1)
    return {
        "starters": starters,
        "bench": bench,
        "total_points": total_points,
        "total_proj": total_proj,
    }


def generate_matchup_data(league: dict, week: int, seed: str | None = None) -> dict:
    seed = seed or f"{league['id']}-{week}-{time.time_ns()}"
    random.seed(_hash_seed(seed))

    teams = random.sample(league["teams"], k=2)
    away_team, home_team = teams[0], teams[1]

    away_lineup = _build_lineup()
    home_lineup = _build_lineup()

    proj_diff = home_lineup["total_proj"] - away_lineup["total_proj"]
    home_prob = max(0.1, min(0.9, 0.5 + (proj_diff / 50.0)))
    away_prob = round(1.0 - home_prob, 2)
    home_prob = round(home_prob, 2)

    trend = []
    base_away = away_lineup["total_proj"]
    base_home = home_lineup["total_proj"]
    for idx in range(6):
        label = f"{idx * 5}m"
        away_proj = round(base_away + random.uniform(-6, 6), 1)
        home_proj = round(base_home + random.uniform(-6, 6), 1)
        away_win = max(0.1, min(0.9, away_prob + random.uniform(-0.06, 0.06)))
        home_win = round(1.0 - away_win, 2)
        trend.append(
            {
                "label": label,
                "away_proj": away_proj,
                "home_proj": home_proj,
                "away_win": round(away_win, 2),
                "home_win": home_win,
            }
        )

    return {
        "week": week,
        "away": {
            "name": away_team["name"],
            "record": away_team["record"],
            "lineup": away_lineup,
        },
        "home": {
            "name": home_team["name"],
            "record": home_team["record"],
            "lineup": home_lineup,
        },
        "win_prob": {"away": away_prob, "home": home_prob},
        "status": _make_status(),
        "trend": trend,
    }
