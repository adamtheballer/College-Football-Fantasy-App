from __future__ import annotations

import hashlib
import random
import time


def _hash_seed(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16], 16)


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


def _make_league_name() -> str:
    name_starts = [
        "Saturday",
        "Campus",
        "Rivalry",
        "Gridiron",
        "Bowl",
        "Tailgate",
        "Heisman",
        "Playoff",
    ]
    name_ends = [
        "Showdown",
        "Clash",
        "Legends",
        "League",
        "Circuit",
        "Cup",
        "Series",
        "Alliance",
    ]
    return f"{random.choice(name_starts)} {random.choice(name_ends)}"


def _make_record() -> str:
    wins = random.randint(2, 7)
    losses = random.randint(0, 5)
    if wins == losses:
        losses = max(0, losses - 1)
    return f"{wins}-{losses}"


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


def _make_news_time() -> str:
    options = ["15m ago", "1h ago", "3h ago", "Yesterday", "2d ago"]
    return random.choice(options)


def generate_home_data(seed: str | None = None) -> dict:
    seed = seed or str(time.time_ns())
    random.seed(_hash_seed(seed))

    league_names = [_make_league_name() for _ in range(random.randint(3, 6))]
    my_teams = []
    for _ in range(random.randint(3, 5)):
        league = random.choice(league_names)
        team_name = _make_team_name()
        my_teams.append(
            {
                "league": league,
                "team": team_name,
                "record": _make_record(),
                "points": f"{random.uniform(980, 1325):.1f}",
                "next_opponent": _make_team_name(),
                "kickoff": f"Week {random.randint(5, 12)} · {random.randint(8, 12):02d}:{random.choice(['00', '30'])} PM",
            }
        )

    matchups = []
    for _ in range(random.randint(3, 5)):
        away = _make_team_name()
        home = _make_team_name()
        matchups.append(
            {
                "away": away,
                "home": home,
                "away_score": random.randint(7, 45),
                "home_score": random.randint(7, 45),
                "status": _make_status(),
                "week": f"Week {random.randint(5, 12)}",
            }
        )

    power_rankings = []
    for rank in range(1, 9):
        trend = random.choice([-2, -1, 0, 1, 2])
        trend_label = f"{trend:+d}" if trend != 0 else "0"
        power_rankings.append(
            {
                "rank": rank,
                "team": _make_team_name(),
                "record": _make_record(),
                "trend": trend_label,
            }
        )

    headlines = [
        "2024 breakout watch: freshmen lighting up the depth chart",
        "Playoff race tightens as rivalry week approaches",
        "Defense wins championships? This league says otherwise",
        "Spotlight: top waiver targets for Week 7",
        "Injury report reshapes the matchup landscape",
        "Start-sit decisions for the weekend slate",
    ]
    league_news = []
    for headline in random.sample(headlines, k=min(len(headlines), random.randint(4, 6))):
        league_news.append(
            {
                "title": headline,
                "summary": f"{_make_team_name()} leads the 2024 surge with a statement win.",
                "source": "ESPN Fantasy",
                "time": _make_news_time(),
            }
        )

    stats = [
        {
            "label": "Season Points",
            "value": f"{random.uniform(4200, 5200):,.1f}",
            "trend": f"+{random.uniform(6.0, 14.0):.1f}%",
            "tone": "primary",
            "icon": "T",
        },
        {
            "label": "Active Leagues",
            "value": f"{random.randint(3, 9):02d}",
            "trend": "+1 New",
            "tone": "emerald",
            "icon": "L",
        },
        {
            "label": "Player Efficiency",
            "value": f"{random.uniform(76.0, 92.0):.1f}%",
            "trend": f"-{random.uniform(1.0, 4.0):.1f}%",
            "tone": "amber",
            "icon": "E",
        },
        {
            "label": "Global Rank",
            "value": f"#{random.randint(900, 1600):,}",
            "trend": f"+{random.randint(120, 520)}",
            "tone": "purple",
            "icon": "R",
        },
    ]

    activity = []
    activity_templates = [
        ("Mike R.", "added", "D. Travis"),
        ("Sarah J.", "dropped", "R. Wilson"),
        ("John D.", "traded", "K. Allen"),
        ("Alex P.", "added", "T. Etienne"),
        ("Chris K.", "dropped", "B. Young"),
        ("Jordan M.", "added", "M. Harrison"),
        ("Avery S.", "traded", "J. Daniels"),
    ]
    for user, action, target in random.sample(activity_templates, k=5):
        activity.append(
            {
                "user": user,
                "action": action,
                "target": target,
                "time": _make_news_time(),
            }
        )

    schedule = [
        {
            "day": "Sat",
            "date": str(random.randint(22, 29)),
            "title": "Waiver Deadline",
            "detail": "11:59 PM ET",
            "tone": "amber",
        },
        {
            "day": "Sat",
            "date": str(random.randint(22, 29)),
            "title": "Weekly Kickoff",
            "detail": (
                f"{_make_team_name()} vs {_make_team_name()} &middot; "
                f"{random.randint(1, 12):02d}:{random.choice(['00', '30'])} PM"
            ),
            "tone": "primary",
        },
        {
            "day": "Tue",
            "date": str(random.randint(22, 29)),
            "title": "Standings Update",
            "detail": "Weekly recaps finalized",
            "tone": "emerald",
        },
    ]

    headlines_feed = []
    players = [
        ("D. Bowers", "WIS", "injury"),
        ("J. Daniels", "LSU", "update"),
        ("M. Harrison", "OSU", "update"),
        ("C. Williams", "USC", "injury"),
    ]
    for player, team, kind in players:
        headlines_feed.append(
            {
                "player": player,
                "team": team,
                "type": kind,
                "time": _make_news_time().upper(),
                "news": f"{_make_team_name()} leads the 2024 surge with a statement win.",
            }
        )

    return {
        "seed": seed,
        "teams": my_teams,
        "matchups": matchups,
        "power_rankings": power_rankings,
        "news": league_news,
        "stats": stats,
        "activity": activity,
        "schedule": schedule,
        "headlines": headlines_feed,
        "session_status": "Live - Active",
    }
