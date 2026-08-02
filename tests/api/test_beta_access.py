from __future__ import annotations

import pytest

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import hash_password
from collegefootballfantasy_api.app.models.beta_access import BetaAccessAuditEvent, BetaAccessCode
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.beta_access import (
    AUDIT_CONCURRENT_REDEMPTION_BLOCKED,
    GENERIC_MISMATCH_MESSAGE,
    beta_access_hmac,
)


TEST_CODE = f"{'EARLY'}-{'ABC123'}"
TEST_EMAIL = "beta-tester@example.com"


@pytest.fixture
def beta_access_enabled():
    original = {
        "enabled": settings.beta_access_enabled,
        "code_secret": settings.beta_access_code_hmac_secret,
        "reservation_secret": settings.beta_access_reservation_secret,
    }
    settings.beta_access_enabled = True
    settings.beta_access_code_hmac_secret = "test-beta-code-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
    settings.beta_access_reservation_secret = "test-beta-reservation-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
    try:
        yield
    finally:
        settings.beta_access_enabled = original["enabled"]
        settings.beta_access_code_hmac_secret = original["code_secret"]
        settings.beta_access_reservation_secret = original["reservation_secret"]


def seed_beta_code(db_session, *, manual_review: bool = False) -> BetaAccessCode:
    record = BetaAccessCode(
        source_waitlist_id="test-waitlist-1",
        email=TEST_EMAIL,
        code_hmac=beta_access_hmac(TEST_CODE, purpose="code"),
        source_status="READY_SENT",
        manual_review=manual_review,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def signup_payload(*, reservation: str | None = None, email: str = TEST_EMAIL) -> dict[str, str]:
    payload = {
        "first_name": "Beta",
        "email": email,
        "password": "StrongPass123!",
    }
    if reservation:
        payload["beta_access_reservation"] = reservation
    return payload


def test_beta_access_requires_valid_reservation_and_redeems_atomically(client, db_session, beta_access_enabled):
    seed_beta_code(db_session)

    direct_signup = client.post("/auth/signup", json=signup_payload())
    assert direct_signup.status_code == 403
    assert direct_signup.json()["detail"] == GENERIC_MISMATCH_MESSAGE

    validation = client.post(
        "/beta-access/validate",
        json={"email": f"  {TEST_EMAIL.upper()}  ", "code": TEST_CODE.lower()},
    )
    assert validation.status_code == 200
    response = validation.json()
    assert response["email"] == TEST_EMAIL
    assert response["existing_account"] is False
    assert TEST_CODE not in validation.text

    # The server derives the account e-mail from the signed reservation, rather
    # than accepting a client-supplied substitute.
    signup = client.post(
        "/auth/signup",
        json=signup_payload(reservation=response["reservation_token"], email="substitute@example.com"),
    )
    assert signup.status_code == 201
    assert signup.json()["user"]["email"] == TEST_EMAIL

    db_session.expire_all()
    record = db_session.query(BetaAccessCode).filter(BetaAccessCode.email == TEST_EMAIL).one()
    user = db_session.query(User).filter(User.email == TEST_EMAIL).one()
    assert record.state == "REDEEMED"
    assert record.redeemed_user_id == user.id
    assert user.beta_access_granted_at is not None

    # Returning users never need to submit an early-access code again.
    login = client.post("/auth/login", json={"email": TEST_EMAIL, "password": "StrongPass123!"})
    assert login.status_code == 200


def test_beta_access_rejects_invalid_manual_review_and_reused_reservations(client, db_session, beta_access_enabled):
    seed_beta_code(db_session)

    mismatch = client.post("/beta-access/validate", json={"email": TEST_EMAIL, "code": f"{'EARLY'}-{'ZZZZZZ'}"})
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"] == GENERIC_MISMATCH_MESSAGE
    assert TEST_CODE not in mismatch.text

    validation = client.post("/beta-access/validate", json={"email": TEST_EMAIL, "code": TEST_CODE})
    assert validation.status_code == 200
    reservation = validation.json()["reservation_token"]
    assert client.post("/auth/signup", json=signup_payload(reservation=reservation)).status_code == 201

    reused = client.post("/auth/signup", json=signup_payload(reservation=reservation))
    assert reused.status_code == 403
    assert reused.json()["detail"] == GENERIC_MISMATCH_MESSAGE
    db_session.expire_all()
    assert (
        db_session.query(BetaAccessAuditEvent)
        .filter(BetaAccessAuditEvent.action == AUDIT_CONCURRENT_REDEMPTION_BLOCKED)
        .count()
        == 1
    )


def test_beta_access_rejects_manual_review_and_malformed_tokens_without_500(client, db_session, beta_access_enabled):
    record = seed_beta_code(db_session, manual_review=True)

    blocked = client.post("/beta-access/validate", json={"email": TEST_EMAIL, "code": TEST_CODE})
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == GENERIC_MISMATCH_MESSAGE

    malformed = client.post("/auth/signup", json=signup_payload(reservation="not.a.valid.reservation"))
    assert malformed.status_code == 403
    assert malformed.json()["detail"] == GENERIC_MISMATCH_MESSAGE

    db_session.refresh(record)
    assert record.state == "AVAILABLE"


def test_beta_access_links_a_verified_code_to_an_existing_account_after_password_login(
    client, db_session, beta_access_enabled
):
    record = seed_beta_code(db_session)
    existing = User(
        first_name="Existing",
        email=TEST_EMAIL,
        username="existing-beta-user",
        password_hash=hash_password("StrongPass123!"),
        api_token="existing-beta-token",
    )
    db_session.add(existing)
    db_session.commit()

    blocked = client.post("/auth/login", json={"email": TEST_EMAIL, "password": "StrongPass123!"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == GENERIC_MISMATCH_MESSAGE

    validation = client.post("/beta-access/validate", json={"email": TEST_EMAIL, "code": TEST_CODE})
    assert validation.status_code == 200

    assert validation.json()["existing_account"] is True
    linked = client.post(
        "/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "StrongPass123!",
            "beta_access_reservation": validation.json()["reservation_token"],
        },
    )
    assert linked.status_code == 200

    db_session.expire_all()
    db_session.refresh(record)
    db_session.refresh(existing)
    assert record.state == "REDEEMED"
    assert record.redeemed_user_id == existing.id
    assert existing.beta_access_granted_at is not None
