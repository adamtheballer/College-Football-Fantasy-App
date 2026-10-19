from __future__ import annotations

import dns.exception
import dns.resolver
import dns.rrset
import pytest

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import hash_password
from collegefootballfantasy_api.app.models.auth_rate_limit_event import AuthRateLimitEvent
from collegefootballfantasy_api.app.models.refresh_session import RefreshSession
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services import signup_email

PASSWORD = "StrongPass123!"


def register(client, email, *, native=False):
    return client.post("/auth/signup", json={"first_name": "Coach", "email": email, "password": PASSWORD},
                       headers={"Origin": "capacitor://localhost", "X-CFFB-Native-Session": "ios"} if native else {})


class DNS:
    def __init__(self, records):
        self.records = records
        self.calls = []

    def resolve(self, domain, kind, *, lifetime):
        assert 0 < lifetime <= settings.signup_email_dns_timeout_seconds
        self.calls.append((domain, kind))
        result = self.records.get(kind, dns.resolver.NoAnswer())
        if isinstance(result, Exception):
            raise result
        return dns.rrset.from_text(domain, 60, "IN", kind, result)


def use_dns(monkeypatch, records):
    resolver = DNS(records)
    monkeypatch.setattr(settings, "signup_email_check_deliverability", True)
    monkeypatch.setattr(signup_email, "_dns_resolver", lambda: resolver)
    return resolver


@pytest.mark.parametrize("email", ["a@@gmail.com", "@gmail.com", "coach@", "a b@gmail.com",
    "a..b@gmail.com", "coach@localhost", "coach@example.invalid", "coach@example.test",
    "coach@[127.0.0.1]", "Coach <coach@gmail.com>", "a" * 65 + "@gmail.com",
    "coach@" + ("a" * 62 + ".") * 3 + "example.com"])
def test_malformed_signup_never_creates_account_or_session(client, db_session, email):
    assert register(client, email).status_code == 422
    assert db_session.query(User).count() == 0
    assert db_session.query(RefreshSession).count() == 0


@pytest.mark.parametrize("email", ["user@mailinator.com", "user@MAILINATOR.COM", "user@sub.mailinator.com",
    "user@yopmail.com", "user@herclan.com", "user@10minutemail.com", "user@guerrillamail.com"])
def test_disposable_providers_blocked_before_dns_for_native_and_web(client, db_session, monkeypatch, email):
    resolver = use_dns(monkeypatch, {})
    response = register(client, email, native=True)
    assert response.status_code == 422
    assert response.json()["detail"] == signup_email.DISPOSABLE_EMAIL
    assert resolver.calls == []
    assert db_session.query(User).count() == 0
    assert db_session.query(RefreshSession).count() == 0
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("email", [" Coach+Fantasy@GMAIL.COM ", "coach@school.edu", "coach@custom.org",
    "relay@privaterelay.appleid.com", "coach@proton.me", "coach@mailinator.com.school.edu", "coach@icloud.com"])
def test_real_providers_aliases_relays_and_custom_domains_allowed(client, monkeypatch, email):
    resolver = use_dns(monkeypatch, {"MX": "10 mail.provider.com."})
    response = register(client, email)
    assert response.status_code == 201
    assert response.json()["user"]["email"] == email.strip().lower()
    assert resolver.calls == [(email.strip().lower().split("@")[1], "MX")]


@pytest.mark.parametrize("records", [{"MX": dns.resolver.NXDOMAIN()}, {"MX": "0 ."}, {}])
def test_nonexistent_or_non_mail_domain_is_rejected(client, db_session, monkeypatch, records):
    use_dns(monkeypatch, records)
    response = register(client, "coach@nonmaildomain.com")
    assert response.status_code == 422
    assert response.json()["detail"] == signup_email.UNDELIVERABLE_EMAIL
    assert db_session.query(User).count() == 0
    assert db_session.query(RefreshSession).count() == 0


@pytest.mark.parametrize("failure", [dns.exception.Timeout(), dns.resolver.NoNameservers(), RuntimeError("resolver failed")])
def test_dns_outage_is_retryable_and_does_not_create_account(client, monkeypatch, failure):
    use_dns(monkeypatch, {"MX": failure})
    response = register(client, "coach@school.edu")
    assert response.status_code == 503
    assert response.json()["detail"] == signup_email.DNS_UNAVAILABLE
    assert response.headers["retry-after"] == "30"
    # A later healthy query must work; transient errors must not poison a
    # permanent email-denial cache.
    use_dns(monkeypatch, {"MX": "10 mail.school.edu."})
    assert register(client, "coach@school.edu").status_code == 201


def test_dns_supports_public_smtp_fallback_and_reject_all_spf(client, monkeypatch):
    use_dns(monkeypatch, {"A": "8.8.8.8"})
    assert register(client, "coach@custom.org").status_code == 201
    use_dns(monkeypatch, {"A": "8.8.8.8", "TXT": '"v=spf1 -all"'})
    assert register(client, "coach@nonmaildomain.com").status_code == 422


def test_dns_budget_is_shared_across_fallbacks(monkeypatch):
    use_dns(monkeypatch, {})
    clock = iter([10.0, 10.1, 14.0])
    monkeypatch.setattr(signup_email, "monotonic", lambda: next(clock))
    with pytest.raises(signup_email.HTTPException) as error:
        signup_email.enforce_signup_email_policy("coach@custom.org")
    assert error.value.status_code == 503


def test_domain_overrides_are_label_scoped_and_do_not_bypass_dns(client, monkeypatch):
    resolver = use_dns(monkeypatch, {"MX": "10 mail.provider.com."})
    monkeypatch.setattr(settings, "signup_email_allowed_domains", " MAILINATOR.COM ")
    assert register(client, "coach@sub.mailinator.com").status_code == 201
    monkeypatch.setattr(settings, "signup_email_blocked_domains", "mailinator.com")
    assert register(client, "coach@mailinator.com").status_code == 422
    assert resolver.calls == [("sub.mailinator.com", "MX")]
    monkeypatch.setattr(settings, "signup_email_blocked_domains", "")
    use_dns(monkeypatch, {"MX": dns.resolver.NXDOMAIN()})
    assert register(client, "coach@mailinator.com").status_code == 422


def test_rejected_addresses_share_durable_signup_ip_limit(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "auth_signup_rate_limit", 2)
    resolver = use_dns(monkeypatch, {})
    assert register(client, "coach@mailinator.com").status_code == 422
    assert register(client, "coach@yopmail.com", native=True).status_code == 422
    assert register(client, "coach@school.edu").status_code == 429
    assert db_session.query(AuthRateLimitEvent).filter_by(action="signup").count() == 2
    assert resolver.calls == []


def test_existing_disposable_account_can_still_sign_in(client, db_session, monkeypatch):
    user = User(first_name="Legacy", email="legacy@mailinator.com", username="legacy-mail",
                password_hash=hash_password(PASSWORD), api_token="legacy-policy-fixture")
    db_session.add(user)
    db_session.commit()
    resolver = use_dns(monkeypatch, {})
    response = client.post("/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    assert resolver.calls == []
