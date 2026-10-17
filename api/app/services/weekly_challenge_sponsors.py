"""Read-only sponsorship by competition season/week, independent of scoring."""
from copy import deepcopy

WEEKLY_CHALLENGE_SPONSORS = {
    (2026, 8): {
        "name": "Pigskin Dispatch",
        "label": "Sponsored by Pigskin Dispatch",
        "tagline": "Football history, stories & podcasts",
        "logo_url": "/assets/sponsors/PigskinDispatchLogo.png",
        "youtube_url": "https://www.youtube.com/channel/UCQatEELNJL5GWry7eMXh-Qg?utm_source=chatgpt.com",
        "season": 2026,
        "week": 8,
    },
}


def weekly_challenge_sponsor(*, season: int, week: int) -> dict | None:
    return deepcopy(WEEKLY_CHALLENGE_SPONSORS.get((season, week)))
