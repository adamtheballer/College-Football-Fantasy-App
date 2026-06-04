from __future__ import annotations


def _combined_text(title: str, summary: str | None = None) -> str:
    return f"{title or ''} {summary or ''}".lower()


def classify_news(title: str, summary: str | None = None) -> str:
    text = _combined_text(title, summary)
    keyword_groups: list[tuple[str, tuple[str, ...]]] = [
        (
            "transfer",
            (
                "transfer",
                "portal",
                "enters portal",
                "entered the portal",
                "commits to",
                "committed to",
                "commitment",
                "signs with",
                "joins",
                "leaving",
                "withdraws from portal",
            ),
        ),
        (
            "injury",
            (
                "injury",
                "injured",
                "out",
                "questionable",
                "doubtful",
                "surgery",
                "return timetable",
                "practice status",
                "limited practice",
            ),
        ),
        (
            "depth_chart",
            (
                "starter",
                "named starter",
                "starting quarterback",
                "qb1",
                "rb1",
                "wr1",
                "depth chart",
                "backup",
                "first-team reps",
            ),
        ),
        (
            "eligibility",
            (
                "eligible",
                "ineligible",
                "suspension",
                "suspended",
                "reinstated",
                "waiver",
            ),
        ),
        (
            "coaching",
            (
                "offensive coordinator",
                "play caller",
                "head coach",
                "coordinator",
                "scheme",
                "offense",
                "air raid",
                "spread offense",
            ),
        ),
        (
            "nfl_draft",
            (
                "nfl draft",
                "draft stock",
                "declares",
                "senior bowl",
                "combine",
            ),
        ),
        (
            "rankings",
            (
                "rankings",
                "top 25",
                "power rankings",
                "preview",
                "prediction",
            ),
        ),
    ]
    for category, keywords in keyword_groups:
        if any(keyword in text for keyword in keywords):
            return category
    return "general"


def category_fantasy_impact(category: str) -> str:
    impacts = {
        "transfer": "Potential role change. Monitor destination, depth chart, and projected usage.",
        "injury": "Availability risk. Check roster exposure before draft or lineup decisions.",
        "depth_chart": "Role clarity update. Could affect fantasy projection and draft value.",
        "coaching": "System change. Watch pace, pass rate, and offensive usage.",
        "eligibility": "Availability update. Confirm status before draft or lineup decisions.",
        "team_news": "Team context update. Monitor player usage and depth chart impact.",
        "nfl_draft": "Roster turnover signal. Watch replacement roles and target share changes.",
        "rankings": "Market context update. Treat as supporting information, not confirmed role news.",
        "general": "Monitor for fantasy relevance before changing rankings or lineups.",
    }
    return impacts.get(category, impacts["general"])
