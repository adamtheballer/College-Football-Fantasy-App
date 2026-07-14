from datetime import datetime, timezone

import pytest

from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import (
    PlayerProviderId,
    ProviderIdentityAudit,
    UnmatchedProviderRow,
)
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.provider_identity import (
    ProviderIdentityConflict,
    record_unmatched_provider_row,
    upsert_player_provider_mapping,
)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str, *, admin: bool = False) -> tuple[str, User]:
    email = f"provider-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Provider{suffix}",
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        user.is_admin = admin
        session.commit()
        user_id = user.id
    with TestingSessionLocal() as session:
        user = session.get(User, user_id)
        assert user is not None
        return response.json()["access_token"], user


def test_unmatched_provider_rows_are_deduped(client, db_session):
    row = {"ESPNPlayerID": "303", "PlayerName": "Bert Auburn", "School": "Texas"}

    first = record_unmatched_provider_row(
        db_session,
        provider="espn",
        feed="weekly_boxscore_player_stats",
        row=row,
        season=2026,
        week=1,
        reason="missing mapping",
    )
    second = record_unmatched_provider_row(
        db_session,
        provider="espn",
        feed="weekly_boxscore_player_stats",
        row=row,
        season=2026,
        week=1,
        reason="missing mapping",
    )
    db_session.commit()

    assert first.id == second.id
    assert db_session.query(UnmatchedProviderRow).count() == 1
    assert second.occurrence_count == 2
    assert second.status == "open"


def test_verified_provider_mapping_cannot_be_silently_reassigned(client, db_session):
    player = Player(name="Arch Manning", position="QB", school="Texas")
    other = Player(name="Other QB", position="QB", school="Texas")
    db_session.add_all([player, other])
    db_session.flush()

    upsert_player_provider_mapping(
        db_session,
        player_id=player.id,
        provider="espn",
        provider_player_id="101",
        verification_status="verified",
        match_confidence=1.0,
        reason="admin verified",
    )

    with pytest.raises(ProviderIdentityConflict):
        upsert_player_provider_mapping(
            db_session,
            player_id=other.id,
            provider="espn",
            provider_player_id="101",
            verification_status="unverified",
            match_confidence=0.5,
            reason="conflicting feed",
        )


def test_admin_can_map_ignore_and_reopen_unmatched_provider_rows(client, db_session):
    admin_token, admin_user = create_user_and_token(client, "admin", admin=True)
    player = Player(name="Bert Auburn", position="K", school="Texas")
    db_session.add(player)
    db_session.flush()
    unmatched = record_unmatched_provider_row(
        db_session,
        provider="espn",
        feed="weekly_boxscore_player_stats",
        row={"ESPNPlayerID": "303", "PlayerName": "Bert Auburn", "School": "Texas"},
        season=2026,
        week=1,
        reason="missing mapping",
    )
    db_session.commit()

    list_response = client.get(
        "/provider-identity/unmatched?status=open",
        headers=auth_headers(admin_token),
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    map_response = client.post(
        f"/provider-identity/unmatched/{unmatched.id}/map",
        json={"player_id": player.id, "match_confidence": 1.0, "reason": "verified ESPN row"},
        headers=auth_headers(admin_token),
    )
    assert map_response.status_code == 200
    assert map_response.json()["status"] == "mapped"
    mapping = db_session.query(PlayerProviderId).filter_by(provider="espn", provider_player_id="303").one()
    assert mapping.player_id == player.id
    assert mapping.verification_status == "verified"
    assert mapping.verified_by_user_id == admin_user.id
    assert db_session.query(ProviderIdentityAudit).filter_by(action="map_to_player").count() == 1

    ignore_response = client.post(
        f"/provider-identity/unmatched/{unmatched.id}/ignore",
        json={"reason": "ignore test"},
        headers=auth_headers(admin_token),
    )
    assert ignore_response.status_code == 200
    assert ignore_response.json()["status"] == "ignored"

    reopen_response = client.post(
        f"/provider-identity/unmatched/{unmatched.id}/reopen",
        json={"reason": "reopen test"},
        headers=auth_headers(admin_token),
    )
    assert reopen_response.status_code == 200
    assert reopen_response.json()["status"] == "open"


def test_non_admin_cannot_access_provider_identity_repair_routes(client):
    token, _user = create_user_and_token(client, "non-admin", admin=False)

    response = client.get("/provider-identity/unmatched", headers=auth_headers(token))

    assert response.status_code == 403
    assert response.json()["detail"] == "admin only"
