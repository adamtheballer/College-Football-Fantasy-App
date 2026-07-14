from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.core.security import generate_token, hash_password, verify_password
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.user import User
from scripts import repair_local_auth_account as repair_script
from tests.conftest import TestingSessionLocal


def test_repair_local_auth_account_resets_hash_and_lockout(client, monkeypatch):
    monkeypatch.setattr(repair_script, "SessionLocal", TestingSessionLocal)
    old_password = "OldStrongPass123!"
    repaired_password = "NewStrongPass123!"

    session = TestingSessionLocal()
    try:
        user = User(
            first_name="Emma",
            email="emmab1167@icloud.com",
            username="emmab1167",
            password_hash=hash_password(old_password),
            api_token=generate_token(32),
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
            failed_login_attempts=settings.auth_failed_login_limit,
            locked_until=datetime.now(timezone.utc) + timedelta(minutes=10),
            last_failed_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
        session.commit()
    finally:
        session.close()

    result = repair_script.repair_local_auth_account(
        email=" EMMAB1167@icloud.com ",
        password=repaired_password,
        first_name="Emma",
    )

    assert result["created"] is False
    assert result["password_changed"] is True
    login_response = client.post(
        "/auth/login",
        json={"email": "emmab1167@icloud.com", "password": repaired_password},
    )
    assert login_response.status_code == 200

    session = TestingSessionLocal()
    try:
        repaired = session.query(User).filter(User.email == "emmab1167@icloud.com").one()
        assert verify_password(repaired_password, repaired.password_hash) is True
        assert repaired.failed_login_attempts == 0
        assert repaired.locked_until is None
        assert repaired.last_failed_login_at is None
        assert repaired.email_verified_at is not None
        assert repaired.is_active is True
    finally:
        session.close()


def test_repair_local_auth_account_creates_missing_verified_user(client, monkeypatch):
    monkeypatch.setattr(repair_script, "SessionLocal", TestingSessionLocal)
    password = "CreatedStrongPass123!"

    result = repair_script.repair_local_auth_account(
        email="missing-local@example.com",
        password=password,
        first_name="Missing",
    )

    assert result["created"] is True
    assert result["password_changed"] is True
    login_response = client.post(
        "/auth/login",
        json={"email": "missing-local@example.com", "password": password},
    )
    assert login_response.status_code == 200
