from __future__ import annotations

from datetime import datetime, timezone


FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K"}
BASE_SCORES = {
    "injury": 80,
    "transfer": 75,
    "depth_chart": 70,
    "eligibility": 65,
    "coaching": 45,
    "team_news": 35,
    "nfl_draft": 30,
    "rankings": 25,
    "commitment": 25,
    "general": 10,
}
ACTION_WORDS = (
    "starter",
    "qb1",
    "rb1",
    "wr1",
    "out",
    "portal",
    "committed",
    "commits",
    "injury",
    "eligible",
)
POWER_FOUR_TEAMS = {
    "Alabama",
    "Arizona",
    "Arizona State",
    "Arkansas",
    "Auburn",
    "Baylor",
    "Boston College",
    "BYU",
    "California",
    "Clemson",
    "Colorado",
    "Duke",
    "Florida",
    "Florida State",
    "Georgia",
    "Georgia Tech",
    "Houston",
    "Illinois",
    "Indiana",
    "Iowa",
    "Iowa State",
    "Kansas",
    "Kansas State",
    "Kentucky",
    "Louisville",
    "LSU",
    "Maryland",
    "Miami",
    "Michigan",
    "Michigan State",
    "Minnesota",
    "Mississippi State",
    "Missouri",
    "Nebraska",
    "North Carolina",
    "NC State",
    "Northwestern",
    "Notre Dame",
    "Ohio State",
    "Oklahoma",
    "Oklahoma State",
    "Ole Miss",
    "Oregon",
    "Penn State",
    "Pittsburgh",
    "Purdue",
    "Rutgers",
    "South Carolina",
    "Stanford",
    "Syracuse",
    "TCU",
    "Tennessee",
    "Texas",
    "Texas A&M",
    "Texas Tech",
    "UCLA",
    "UCF",
    "USC",
    "Utah",
    "Vanderbilt",
    "Virginia",
    "Virginia Tech",
    "Wake Forest",
    "Washington",
    "West Virginia",
    "Wisconsin",
}


def compute_fantasy_relevance(
    *,
    category: str,
    title: str,
    summary: str | None = None,
    published_at: datetime | None = None,
    player_id: int | None = None,
    canonical_team: str | None = None,
    position: str | None = None,
    now: datetime | None = None,
) -> float:
    score = float(BASE_SCORES.get(category, BASE_SCORES["general"]))
    text = f"{title or ''} {summary or ''}".lower()
    now = now or datetime.now(timezone.utc)
    if player_id is not None:
        score += 20
    if (position or "").upper() in FANTASY_POSITIONS:
        score += 15
    if canonical_team in POWER_FOUR_TEAMS:
        score += 10
    if published_at:
        published = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
        if (now - published.astimezone(timezone.utc)).total_seconds() <= 86_400:
            score += 10
    if any(word in text for word in ACTION_WORDS):
        score += 10
    return max(0.0, min(100.0, score))
