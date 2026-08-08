from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from scripts import import_beta_access_waitlist as importer
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.services.auth_security import utcnow
from collegefootballfantasy_api.app.services.beta_access import beta_access_hmac


class Query:
    def __init__(self, rows): self.rows = rows
    def filter(self, *args): return self
    def all(self): return list(self.rows)


class FakeSession:
    def __init__(self, beta_rows=(), users=()):
        self.beta_rows, self.users = list(beta_rows), list(users)
    def __enter__(self): return self
    def __exit__(self, *args): return None
    def query(self, model):
        return Query(self.beta_rows if model.__name__ == "BetaAccessCode" else self.users)


@pytest.fixture(autouse=True)
def fake_hmac_secret(monkeypatch):
    monkeypatch.setattr(settings, "beta_access_code_hmac_secret", "test-only-reconciliation-secret")


def row(*, email="invite@example.com", code="EARLY-ABC123", status="READY_SENT", manual_review=False):
    return importer.ParsedRow("source-1", email, code, status, None, manual_review, None, None, "SENT", None, None, None, None)


def beta(*, state="AVAILABLE", matching=True, manual_review=False, source_status="READY_SENT", expires=None, redeemed_user_id=None):
    return SimpleNamespace(
        id=7, state=state, manual_review=manual_review, source_status=source_status,
        code_hmac="test-code-hmac" if matching else "different-test-code-hmac",
        reservation_expires_at=expires, redeemed_user_id=redeemed_user_id,
    )


def classify(monkeypatch, source, beta_rows=(), users=()):
    monkeypatch.setattr(importer, "SessionLocal", lambda: FakeSession(beta_rows, users))
    monkeypatch.setattr(importer, "beta_access_hmac", lambda value, *, purpose: "test-code-hmac")
    return importer.reconciliation_report([source])


@pytest.mark.parametrize(
    ("source", "beta_rows", "users", "expected"),
    [
        (row(), [beta()], [], "MATCHED"),
        (row(), [beta(matching=False)], [], "NEEDS_HMAC_RECONCILIATION"),
        (row(), [beta(state="RESERVED", expires=utcnow() + timedelta(minutes=5))], [], "RESERVED_ACTIVE"),
        (row(), [beta(state="RESERVED", expires=utcnow() - timedelta(minutes=5))], [], "RESERVED_EXPIRED"),
        (row(), [], [], "MISSING_PRODUCTION_ROW"),
        (row(), [beta(), beta()], [], "DUPLICATE_PRODUCTION_ROW"),
        (row(status="SKIPPED_SUPPRESSED"), [], [], "SUPPRESSED"),
        (row(code=None, status="INVALID_CODE"), [], [], "PENDING_NO_CODE"),
        (row(email=None, status="INVALID_EMAIL"), [], [], "INVALID_SOURCE"),
    ],
)
def test_each_non_user_reconciliation_category(monkeypatch, source, beta_rows, users, expected):
    outcomes, reviews = classify(monkeypatch, source, beta_rows, users)
    assert outcomes[expected] == 1
    assert all("EARLY-" not in str(item) for item in reviews)


def test_redeemed_preserved_and_wrong_link_conflicts(monkeypatch):
    user = SimpleNamespace(id=3, beta_access_granted_at=utcnow())
    outcomes, _ = classify(monkeypatch, row(), [beta(state="REDEEMED", redeemed_user_id=3)], [user])
    assert outcomes["REDEEMED_PRESERVE"] == 1
    outcomes, _ = classify(monkeypatch, row(), [beta(state="REDEEMED", redeemed_user_id=4)], [user])
    assert outcomes["CONFLICT"] == 1


@pytest.mark.parametrize(
    ("beta_row", "users"),
    [
        (beta(manual_review=True), []),
        (beta(), [SimpleNamespace(id=1, beta_access_granted_at=utcnow())]),
        (beta(), [SimpleNamespace(id=1, beta_access_granted_at=None), SimpleNamespace(id=2, beta_access_granted_at=None)]),
    ],
)
def test_unsafe_user_or_metadata_states_conflict(monkeypatch, beta_row, users):
    outcomes, _ = classify(monkeypatch, row(), [beta_row], users)
    assert outcomes["CONFLICT"] == 1


def test_all_categories_present_and_dry_run_has_no_write_methods(monkeypatch):
    outcomes, reviews = classify(monkeypatch, row(), [beta()], [])
    assert set(importer.RECONCILIATION_CATEGORIES) == set(outcomes)
    assert reviews == []
    assert outcomes["MATCHED"] == 1


def test_apply_is_refused(monkeypatch):
    monkeypatch.setattr(importer, "parse_args", lambda: SimpleNamespace(rekey_code_hmac=False, verify_only=False, source=__file__, apply=True, report_path=None))
    with pytest.raises(ValueError, match="--apply is disabled"):
        importer.main()
