from scripts.import_espn_live_identities import _event_facts


def test_event_facts_accepts_authoritative_summary_integer_week() -> None:
    """ESPN summaries use an integer week while scoreboards use an object."""

    event = {
        "id": "401858425",
        "week": 1,
        "date": "2026-09-05T16:00Z",
        "competitions": [
            {
                "competitors": [
                    {"homeAway": "home", "team": {"id": "84", "location": "Indiana"}},
                    {"homeAway": "away", "team": {"id": "249", "location": "North Texas"}},
                ]
            }
        ],
    }

    assert _event_facts(event, season=2026, requested_week=1) == {
        "espn_event_id": "401858425",
        "season": 2026,
        "week": 1,
        "home_team": "Indiana",
        "away_team": "North Texas",
        "home_team_id": "84",
        "away_team_id": "249",
        "kickoff": "2026-09-05T16:00:00+00:00",
        "status": "scheduled",
    }
