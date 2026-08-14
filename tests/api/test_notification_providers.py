import httpx
import pytest

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.services import notification_providers
from collegefootballfantasy_api.app.services.notification_providers import OneSignalPushProvider, ResendEmailProvider


class _Response:
    def __init__(self, status_code: int, payload: object | None = None):
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}" if payload is not None else b""

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.mark.parametrize("status_code,retryable", [(400, False), (401, False), (429, True), (500, True)])
def test_onesignal_provider_sanitizes_non_success_responses(monkeypatch, status_code, retryable):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_app_api_key", "secret-key")
    monkeypatch.setattr(
        notification_providers.httpx,
        "post",
        lambda *_args, **_kwargs: _Response(status_code, {"errors": ["opaque provider diagnostic"]}),
    )

    result = OneSignalPushProvider().send(
        external_user_id="cfb_user:1",
        title="Title",
        body="Body",
        data={},
        idempotency_key="provider-idempotency-key",
    )

    assert result.accepted is False
    assert result.retryable is retryable
    assert result.error == f"OneSignal rejected notification (HTTP {status_code})"


def test_provider_timeout_is_retryable_and_success_without_json_still_accepts(monkeypatch):
    monkeypatch.setattr(settings, "onesignal_app_id", "app-id")
    monkeypatch.setattr(settings, "onesignal_app_api_key", "secret-key")
    monkeypatch.setattr(
        notification_providers.httpx,
        "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(httpx.TimeoutException("timeout")),
    )
    timeout = OneSignalPushProvider().send(
        external_user_id="cfb_user:1", title="Title", body="Body", data={}, idempotency_key="timeout-key"
    )
    assert timeout.accepted is False and timeout.retryable is True

    monkeypatch.setattr(notification_providers.httpx, "post", lambda *_args, **_kwargs: _Response(200, ValueError("bad json")))
    accepted = OneSignalPushProvider().send(
        external_user_id="cfb_user:1", title="Title", body="Body", data={}, idempotency_key="accepted-key"
    )
    assert accepted.accepted is True
    assert accepted.provider_message_id is None


def test_resend_uses_provider_idempotency_and_sanitized_failures(monkeypatch):
    monkeypatch.setattr(settings, "resend_api_key", "resend-secret")
    monkeypatch.setattr(settings, "resend_from", "alerts@example.test")
    observed: dict = {}

    def post(*_args, **kwargs):
        observed.update(kwargs)
        return _Response(500, {"error": "do not persist provider payload"})

    monkeypatch.setattr(notification_providers.httpx, "post", post)
    result = ResendEmailProvider().send(
        email="manager@example.test", title="Title", body="Body", idempotency_key="email-key"
    )
    assert observed["headers"]["Idempotency-Key"] == "email-key"
    assert result.accepted is False and result.retryable is True
    assert result.error == "Resend rejected notification (HTTP 500)"
