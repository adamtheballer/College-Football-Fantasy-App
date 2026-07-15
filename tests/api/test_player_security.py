from collegefootballfantasy_api.app.core.security import create_access_token, generate_token, hash_password
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User


def _admin_headers(db_session) -> dict[str, str]:
    admin = User(
        first_name="Admin",
        email="admin@example.com",
        username="admin",
        password_hash=hash_password("StrongPass123!"),
        api_token=generate_token(32),
        is_admin=True,
    )
    db_session.add(admin)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(user_id=admin.id, email=admin.email)[0]}"}


def test_player_creation_requires_admin(client, db_session):
    payload = [{"name": "Secure Player", "position": "QB", "school": "Texas"}]
    assert client.post("/players", json=payload).status_code == 401

    signup = client.post(
        "/auth/signup",
        json={"first_name": "Coach", "email": "coach@example.com", "password": "StrongPass123!"},
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    assert client.post("/players", json=payload, headers={"Authorization": f"Bearer {token}"}).status_code == 403

    created = client.post("/players", json=payload, headers=_admin_headers(db_session))
    assert created.status_code == 201


def test_player_refresh_requires_admin(client, db_session):
    player = Player(name="Cached Player", position="RB", school="Oregon", external_id="123")
    db_session.add(player)
    db_session.commit()

    assert client.get(f"/players/{player.id}/stats?refresh=true").status_code == 403
    admin_response = client.get(f"/players/{player.id}/stats?refresh=true", headers=_admin_headers(db_session))
    assert admin_response.status_code in {200, 502}
