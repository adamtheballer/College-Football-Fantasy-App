from collegefootballfantasy_api.app.core.security import create_access_token, generate_token, hash_password
from collegefootballfantasy_api.app.core.config import settings
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


def test_guest_can_browse_players_and_open_cached_player_cards(client, db_session):
    player = Player(name="Guest Board Player", position="WR", school="Ohio State", cfb27_rank=1)
    db_session.add(player)
    db_session.commit()

    board_response = client.get("/players", params={"sort": "rank", "limit": 10})
    assert board_response.status_code == 200
    assert [row["id"] for row in board_response.json()["data"]] == [player.id]

    card_response = client.get(f"/players/{player.id}/card")
    assert card_response.status_code == 200
    assert card_response.json()["player"]["id"] == player.id


def test_public_beta_hides_existing_player_headshots_without_removing_player_data(client, db_session):
    player = Player(
        name="Portrait Compliance Player",
        position="WR",
        school="Ohio State",
        cfb27_rank=1,
        image_url="https://assets.espn.test/player.png",
        espn_headshot_url="https://assets.espn.test/profile.png",
    )
    db_session.add(player)
    db_session.commit()

    board_response = client.get("/players", params={"sort": "rank", "limit": 10})
    card_response = client.get(f"/players/{player.id}/card")

    assert board_response.status_code == 200
    assert card_response.status_code == 200
    assert board_response.json()["data"][0]["image_url"] is None
    assert card_response.json()["player"]["image_url"] is None
    assert card_response.json()["about"]["headshot_url"] is None
    db_session.refresh(player)
    assert player.image_url == "https://assets.espn.test/player.png"
    assert player.espn_headshot_url == "https://assets.espn.test/profile.png"


def test_player_headshot_flag_can_restore_the_existing_nullable_api_contract(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "player_headshots_enabled", True)
    player = Player(
        name="Licensed Portrait Player",
        position="QB",
        school="Texas",
        cfb27_rank=1,
        image_url="https://licensed.example/player.png",
    )
    db_session.add(player)
    db_session.commit()

    response = client.get("/players", params={"sort": "rank", "limit": 10})

    assert response.status_code == 200
    assert response.json()["data"][0]["image_url"] == "https://licensed.example/player.png"


def test_public_beta_refuses_new_player_headshot_writes(client, db_session):
    response = client.post(
        "/players",
        json=[
            {
                "name": "New Portrait Attempt",
                "position": "RB",
                "school": "Texas",
                "image_url": "https://assets.espn.test/new-player.png",
            }
        ],
        headers=_admin_headers(db_session),
    )

    assert response.status_code == 201
    assert response.json()[0]["image_url"] is None
    created = db_session.get(Player, response.json()[0]["id"])
    assert created is not None
    assert created.image_url is None


def test_player_refresh_requires_admin(client, db_session):
    player = Player(name="Cached Player", position="RB", school="Oregon", external_id="123")
    db_session.add(player)
    db_session.commit()

    assert client.get(f"/players/{player.id}/stats?refresh=true").status_code == 403
    admin_response = client.get(f"/players/{player.id}/stats?refresh=true", headers=_admin_headers(db_session))
    assert admin_response.status_code in {200, 502}
