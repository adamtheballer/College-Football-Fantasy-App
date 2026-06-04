def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_me_requires_token(client):
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_auth_me_returns_current_user_after_login(client):
    signup_payload = {
        "first_name": "Phase",
        "email": "phase2@example.com",
        "password": "password123",
    }
    signup_response = client.post("/auth/signup", json=signup_payload)
    assert signup_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": signup_payload["email"], "password": signup_payload["password"]},
    )
    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]
    response = client.get("/auth/me", headers=auth_headers(access_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == login_response.json()["user"]["id"]
    assert payload["first_name"] == signup_payload["first_name"]
    assert payload["email"] == signup_payload["email"]
    assert "created_at" in payload


def test_auth_me_rejects_invalid_token(client):
    response = client.get("/auth/me", headers=auth_headers("not-a-valid-token"))

    assert response.status_code == 401
