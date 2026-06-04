def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client) -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": "Query",
            "email": "query-validation@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def test_list_endpoint_rejects_negative_offset(client):
    token = create_user_and_token(client)

    response = client.get("/leagues?offset=-1", headers=auth_headers(token))

    assert response.status_code == 422


def test_list_endpoint_rejects_huge_limit(client):
    token = create_user_and_token(client)

    response = client.get("/leagues?limit=100000", headers=auth_headers(token))

    assert response.status_code == 422


def test_list_endpoint_accepts_normal_request(client):
    token = create_user_and_token(client)

    response = client.get("/leagues?limit=50&offset=0", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["limit"] == 50
    assert response.json()["offset"] == 0
