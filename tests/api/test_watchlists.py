def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_player(client, name: str = "Watch Player") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": "WR",
                "school": "USC",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def test_watchlists_persist_per_user(client):
    token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    player_id = create_player(client)

    create_response = client.post(
        "/watchlists",
        json={"name": "Targets"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 201
    watchlist = create_response.json()

    add_response = client.post(
        f"/watchlists/{watchlist['id']}/players",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert add_response.status_code == 200
    assert add_response.json()["players"][0]["id"] == player_id

    owner_list_response = client.get("/watchlists", headers=auth_headers(token))
    assert owner_list_response.status_code == 200
    assert owner_list_response.json()["total"] == 1
    assert owner_list_response.json()["data"][0]["players"][0]["id"] == player_id

    outsider_list_response = client.get("/watchlists", headers=auth_headers(outsider_token))
    assert outsider_list_response.status_code == 200
    assert outsider_list_response.json()["total"] == 0

    outsider_add_response = client.post(
        f"/watchlists/{watchlist['id']}/players",
        json={"player_id": player_id},
        headers=auth_headers(outsider_token),
    )
    assert outsider_add_response.status_code == 404
