from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.mock_draft import MockDraft
from collegefootballfantasy_api.app.models.mock_draft_pick import MockDraftPick
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.transaction import Transaction


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "mock") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Mock{suffix}",
            "email": f"mock-{suffix}@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_players(client) -> list[dict]:
    response = client.post(
        "/players",
        json=[
            {
                "name": "Ahmad Hardy",
                "position": "RB",
                "school": "Missouri",
                "sheet_adp": 1,
                "sheet_projected_season_points": 347.4,
            },
            {
                "name": "Jeremiah Smith",
                "position": "WR",
                "school": "Ohio State",
                "sheet_adp": 2,
                "sheet_projected_season_points": 342.8,
            },
            {
                "name": "Cade Klubnik",
                "position": "QB",
                "school": "Clemson",
                "sheet_adp": 3,
                "sheet_projected_season_points": 315.0,
            },
        ],
    )
    assert response.status_code == 201
    return response.json()


def create_real_league(client, token: str) -> dict:
    payload = {
        "basics": {
            "name": "Real League Must Stay Untouched",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": None,
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5, "IR": 1},
            "playoff_teams": 4,
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


def real_mutation_counts(db_session) -> dict[str, int]:
    return {
        "draft_picks": db_session.query(DraftPick).count(),
        "roster_entries": db_session.query(RosterEntry).count(),
        "transactions": db_session.query(Transaction).count(),
        "standings": db_session.query(Standing).count(),
    }


def test_mock_draft_create_is_isolated_from_real_league_state(client, db_session):
    token = create_user_and_token(client, "create")
    create_real_league(client, token)
    before_counts = real_mutation_counts(db_session)
    league_statuses = [league.status for league in db_session.query(League).all()]
    draft_statuses = [draft.status for draft in db_session.query(Draft).all()]

    response = client.post(
        "/mock-drafts",
        json={"title": "Practice Room", "league_size": 4, "rounds": 2},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Practice Room"
    assert db_session.query(MockDraft).count() == 1
    assert db_session.query(MockDraftPick).count() == 0
    assert real_mutation_counts(db_session) == before_counts
    assert [league.status for league in db_session.query(League).all()] == league_statuses
    assert [draft.status for draft in db_session.query(Draft).all()] == draft_statuses


def test_mock_pick_creates_only_mock_pick_not_real_roster_or_draft_pick(client, db_session):
    token = create_user_and_token(client, "pick")
    players = create_players(client)
    create_real_league(client, token)
    draft_response = client.post(
        "/mock-drafts",
        json={"league_size": 4, "rounds": 2},
        headers=auth_headers(token),
    )
    mock_draft_id = draft_response.json()["id"]
    before_counts = real_mutation_counts(db_session)

    response = client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[0]["id"]},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["current_pick"] == 2
    assert len(body["picks"]) == 1
    assert body["picks"][0]["player_name"] == "Ahmad Hardy"
    assert db_session.query(MockDraftPick).count() == 1
    assert real_mutation_counts(db_session) == before_counts


def test_duplicate_mock_pick_returns_409_without_extra_mock_pick_or_real_mutation(client, db_session):
    token = create_user_and_token(client, "duplicate")
    players = create_players(client)
    draft_response = client.post(
        "/mock-drafts",
        json={"league_size": 4, "rounds": 2},
        headers=auth_headers(token),
    )
    mock_draft_id = draft_response.json()["id"]
    first = client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[0]["id"]},
        headers=auth_headers(token),
    )
    assert first.status_code == 200
    before_counts = real_mutation_counts(db_session)

    duplicate = client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[0]["id"]},
        headers=auth_headers(token),
    )

    assert duplicate.status_code == 409
    assert db_session.query(MockDraftPick).count() == 1
    assert real_mutation_counts(db_session) == before_counts


def test_reset_mock_draft_deletes_only_mock_picks(client, db_session):
    token = create_user_and_token(client, "reset")
    players = create_players(client)
    create_real_league(client, token)
    draft_response = client.post(
        "/mock-drafts",
        json={"league_size": 4, "rounds": 2},
        headers=auth_headers(token),
    )
    mock_draft_id = draft_response.json()["id"]
    client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[0]["id"]},
        headers=auth_headers(token),
    )
    before_counts = real_mutation_counts(db_session)

    response = client.post(f"/mock-drafts/{mock_draft_id}/reset", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["current_pick"] == 1
    assert response.json()["status"] == "active"
    assert db_session.query(MockDraftPick).count() == 0
    assert real_mutation_counts(db_session) == before_counts


def test_mock_completion_does_not_mutate_real_draft_or_league_status(client, db_session):
    token = create_user_and_token(client, "complete")
    players = create_players(client)
    create_real_league(client, token)
    draft_response = client.post(
        "/mock-drafts",
        json={"league_size": 2, "rounds": 1},
        headers=auth_headers(token),
    )
    mock_draft_id = draft_response.json()["id"]
    league_statuses = [league.status for league in db_session.query(League).all()]
    draft_statuses = [draft.status for draft in db_session.query(Draft).all()]
    before_counts = real_mutation_counts(db_session)

    first = client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[0]["id"]},
        headers=auth_headers(token),
    )
    second = client.post(
        f"/mock-drafts/{mock_draft_id}/picks",
        json={"player_id": players[1]["id"]},
        headers=auth_headers(token),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "completed"
    assert db_session.query(MockDraftPick).count() == 2
    assert real_mutation_counts(db_session) == before_counts
    assert [league.status for league in db_session.query(League).all()] == league_statuses
    assert [draft.status for draft in db_session.query(Draft).all()] == draft_statuses
