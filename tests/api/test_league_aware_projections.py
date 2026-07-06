from datetime import datetime, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> str:
    email = f"projection-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Projection{suffix}",
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return response.json()["access_token"]


def create_league(client, token: str, suffix: str, scoring_json: dict) -> dict:
    payload = {
        "basics": {
            "name": f"Projection League {suffix}",
            "season_year": 2026,
            "max_teams": 2,
            "is_private": True,
            "description": None,
            "icon_url": None,
        },
        "settings": {
            "scoring_json": scoring_json,
            "roster_slots_json": {"QB": 1, "WR": 1},
            "playoff_teams": 2,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": True,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }
    response = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def create_projection(position: str = "WR") -> tuple[int, int]:
    with TestingSessionLocal() as session:
        player = Player(name=f"Projected {position}", position=position, school="Test State", external_id=None)
        session.add(player)
        session.flush()
        projection = WeeklyProjection(
            player_id=player.id,
            season=2026,
            week=1,
            pass_attempts=0.0,
            rush_attempts=0.0,
            targets=8.0,
            receptions=5.0,
            expected_plays=8.0,
            expected_rush_per_play=0.0,
            expected_td_per_play=0.125,
            pass_yards=0.0,
            rush_yards=0.0,
            rec_yards=75.0,
            pass_tds=0.0,
            rush_tds=0.0,
            rec_tds=1.0,
            interceptions=0.0,
            fantasy_points=18.5,
            floor=9.25,
            ceiling=27.75,
            boom_prob=0.2,
            bust_prob=0.1,
        )
        session.add(projection)
        session.commit()
        return player.id, projection.id


def create_qb_projection() -> int:
    with TestingSessionLocal() as session:
        player = Player(name="Projected QB", position="QB", school="Test State", external_id=None)
        session.add(player)
        session.flush()
        projection = WeeklyProjection(
            player_id=player.id,
            season=2026,
            week=1,
            pass_attempts=30.0,
            rush_attempts=0.0,
            targets=0.0,
            receptions=0.0,
            expected_plays=30.0,
            expected_rush_per_play=0.0,
            expected_td_per_play=0.0667,
            pass_yards=250.0,
            rush_yards=0.0,
            rec_yards=0.0,
            pass_tds=2.0,
            rush_tds=0.0,
            rec_tds=0.0,
            interceptions=1.0,
            fantasy_points=16.0,
            floor=8.0,
            ceiling=24.0,
            boom_prob=0.2,
            bust_prob=0.1,
        )
        session.add(projection)
        session.commit()
        return player.id


def test_projection_without_league_id_returns_default_fantasy_points(client):
    player_id, _ = create_projection()

    response = client.get(f"/projections/{player_id}", params={"season": 2026, "week": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["fantasy_points"] == 18.5
    assert payload["league_fantasy_points"] is None
    assert payload["scoring_context"] is None


def test_projection_without_league_id_ignores_invalid_auth_header(client):
    player_id, _ = create_projection()

    response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 200
    assert response.json()["fantasy_points"] == 18.5
    assert response.json()["league_fantasy_points"] is None


def test_projection_with_league_id_returns_league_fantasy_points(client):
    token = create_user_and_token(client, "member")
    league = create_league(client, token, "ppr", {"ppr": 1})
    player_id, _ = create_projection()

    response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1, "league_id": league["id"]},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fantasy_points"] == 18.5
    assert payload["league_fantasy_points"] == 18.5
    assert payload["league_breakdown_json"]["receptions"]["points"] == 5.0
    assert payload["scoring_context"] == "league"


def test_projection_with_league_id_requires_auth(client):
    token = create_user_and_token(client, "requires-auth-owner")
    league = create_league(client, token, "requires-auth", {"ppr": 1})
    player_id, _ = create_projection()

    response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1, "league_id": league["id"]},
    )

    assert response.status_code == 401


def test_custom_ppr_changes_league_fantasy_points_without_changing_stat_line(client):
    token = create_user_and_token(client, "owner")
    ppr_league = create_league(client, token, "full-ppr", {"ppr": 1})
    standard_league = create_league(client, token, "standard", {"ppr": 0})
    player_id, _ = create_projection()

    ppr_response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1, "league_id": ppr_league["id"]},
        headers=auth_headers(token),
    )
    standard_response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1, "league_id": standard_league["id"]},
        headers=auth_headers(token),
    )

    assert ppr_response.status_code == 200
    assert standard_response.status_code == 200
    ppr_payload = ppr_response.json()
    standard_payload = standard_response.json()
    assert ppr_payload["league_fantasy_points"] == 18.5
    assert standard_payload["league_fantasy_points"] == 13.5
    assert ppr_payload["receptions"] == standard_payload["receptions"] == 5.0
    assert ppr_payload["rec_yards"] == standard_payload["rec_yards"] == 75.0
    assert ppr_payload["fantasy_points"] == standard_payload["fantasy_points"] == 18.5


def test_custom_passing_td_changes_qb_league_fantasy_points(client):
    token = create_user_and_token(client, "qb-owner")
    four_point_league = create_league(client, token, "four-pass-td", {"pass_td": 4})
    six_point_league = create_league(client, token, "six-pass-td", {"pass_td": 6})
    player_id = create_qb_projection()

    four_point_response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1, "league_id": four_point_league["id"]},
        headers=auth_headers(token),
    )
    six_point_response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1, "league_id": six_point_league["id"]},
        headers=auth_headers(token),
    )

    assert four_point_response.status_code == 200
    assert six_point_response.status_code == 200
    assert four_point_response.json()["league_fantasy_points"] == 16.0
    assert six_point_response.json()["league_fantasy_points"] == 20.0


def test_non_member_cannot_request_league_specific_projection(client):
    owner_token = create_user_and_token(client, "league-owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token, "private", {"ppr": 1})
    player_id, _ = create_projection()

    response = client.get(
        f"/projections/{player_id}",
        params={"season": 2026, "week": 1, "league_id": league["id"]},
        headers=auth_headers(outsider_token),
    )

    assert response.status_code == 403


def test_projection_list_adds_league_fields_only_when_league_id_is_provided(client):
    token = create_user_and_token(client, "list-owner")
    league = create_league(client, token, "list", {"ppr": 0})
    create_projection()

    public_response = client.get("/projections", params={"season": 2026, "week": 1})
    league_response = client.get(
        "/projections",
        params={"season": 2026, "week": 1, "league_id": league["id"]},
        headers=auth_headers(token),
    )

    assert public_response.status_code == 200
    assert league_response.status_code == 200
    assert public_response.json()["data"][0]["league_fantasy_points"] is None
    assert league_response.json()["data"][0]["league_fantasy_points"] == 13.5
