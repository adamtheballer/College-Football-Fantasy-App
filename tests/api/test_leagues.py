
def test_create_and_list_leagues(client):
    payload = {"name": "Test League", "platform": "espn", "scoring_type": "standard"}
    response = client.post("/leagues", json=payload)
    assert response.status_code == 201

    response = client.get("/leagues")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["name"] == "Test League"


def test_create_team_under_league(client):
    league_payload = {"name": "Team League", "platform": "yahoo", "scoring_type": "ppr"}
    league_response = client.post("/leagues", json=league_payload)
    league_id = league_response.json()["id"]

    team_payload = {"name": "A Team", "owner_name": "Owner"}
    response = client.post(f"/leagues/{league_id}/teams", json=team_payload)
    assert response.status_code == 201

    response = client.get(f"/leagues/{league_id}/teams")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["name"] == "A Team"
