from datetime import datetime, timedelta, timezone

import pytest

from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.injury_status import normalize_injury_status


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("TBD", "TBD"),
        ("Questionable", "QUESTIONABLE"),
        ("Doubtful", "DOUBTFUL"),
        ("Out", "OUT"),
        ("Out for Season", "OUT_FOR_SEASON"),
        ("Day-to-Day", "DAY_TO_DAY"),
        ("Suspended", "SUSPENDED"),
        ("Inactive", "INACTIVE"),
        ("IR", "IR"),
        ("Active", "FULL"),
        ("N/A", "N_A"),
    ],
)
def test_normalize_injury_status_recognizes_reviewed_designations(raw_status, expected):
    assert normalize_injury_status(raw_status) == expected


def test_player_card_prefers_current_reviewed_injury_over_espn_availability(client, db_session):
    player = Player(name="Current Injury", position="RB", school="Georgia", espn_status="Active")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        Injury(
            player_id=player.id,
            season=2026,
            week=1,
            status="OUT",
            injury="Hamstring",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/card?injury_season=2026&injury_week=1")

    assert response.status_code == 200
    body = response.json()
    assert body["about"]["status"] == "Active"
    assert body["current_injury_status"] == "OUT"
    assert body["injuries"][0]["status"] == "OUT"


def test_player_card_uses_newest_current_reviewed_record_and_ignores_old_weeks(client, db_session):
    player = Player(name="Reviewed Status", position="WR", school="Alabama", espn_status="Active")
    db_session.add(player)
    db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            Injury(
                player_id=player.id,
                season=2025,
                week=15,
                status="OUT_FOR_SEASON",
                updated_at=now - timedelta(days=10),
            ),
            Injury(
                player_id=player.id,
                season=2026,
                week=1,
                status="QUESTIONABLE",
                updated_at=now - timedelta(hours=1),
            ),
            Injury(
                player_id=player.id,
                season=2026,
                week=1,
                status="OUT",
                updated_at=now,
            ),
        ]
    )
    db_session.commit()

    current = client.get(f"/players/{player.id}/card?injury_season=2026&injury_week=1")
    next_week = client.get(f"/players/{player.id}/card?injury_season=2026&injury_week=2")

    assert current.status_code == 200
    assert current.json()["current_injury_status"] == "OUT"
    assert next_week.status_code == 200
    assert next_week.json()["current_injury_status"] is None


def test_player_card_resolved_current_injury_returns_normal_availability(client, db_session):
    player = Player(name="Resolved Injury", position="QB", school="Texas", espn_status="Available")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        Injury(
            player_id=player.id,
            season=2026,
            week=1,
            status="FULL",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/card?injury_season=2026&injury_week=1")

    assert response.status_code == 200
    assert response.json()["current_injury_status"] is None
    assert response.json()["about"]["status"] == "Available"
