"""Provider boundaries for durable notification delivery.

Only this module is allowed to make notification-provider HTTP requests. The
worker records the result after a provider accepts or rejects a message; domain
services only enqueue notification events in their database transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import logging
import httpx

from collegefootballfantasy_api.app.core.config import settings


class _ProviderRequestFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Provider identity URLs contain opaque subscription IDs. Keep them out of routine HTTP logs.
        return "api.onesignal.com" not in record.getMessage()

logging.getLogger("httpx").addFilter(_ProviderRequestFilter())


@dataclass(frozen=True)
class ProviderDeliveryResult:
    accepted: bool
    provider_message_id: str | None = None
    retryable: bool = False
    invalid_subscription_id: str | None = None
    error: str | None = None


class PushNotificationProvider(Protocol):
    def send(
        self,
        *,
        external_user_id: str,
        subscription_id: str,
        ttl: int = 3600,
        badge_count: int = 0,
        private_alert: bool = False,
        title: str,
        body: str,
        data: dict,
        idempotency_key: str,
    ) -> ProviderDeliveryResult: ...


class EmailNotificationProvider(Protocol):
    def send(
        self,
        *,
        email: str,
        title: str,
        body: str,
        idempotency_key: str,
    ) -> ProviderDeliveryResult: ...


class DisabledPushProvider:
    def send(self, **_: object) -> ProviderDeliveryResult:
        return ProviderDeliveryResult(accepted=False, error="push delivery is disabled")


class FakePushProvider:
    """No-network provider used by unit and real-stack tests."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, **payload: object) -> ProviderDeliveryResult:
        self.messages.append(payload)
        return ProviderDeliveryResult(accepted=True, provider_message_id=str(payload["idempotency_key"]))


class OneSignalPushProvider:
    endpoint = "https://api.onesignal.com/notifications"

    def send(
        self,
        *,
        external_user_id: str,
        subscription_id: str,
        ttl: int = 3600,
        badge_count: int = 0,
        private_alert: bool = False,
        title: str,
        body: str,
        data: dict,
        idempotency_key: str,
    ) -> ProviderDeliveryResult:
        if not settings.onesignal_app_id or not settings.onesignal_app_api_key:
            # The settings validator prevents this in enabled configurations.
            # Keep this defensive guard secret-safe for direct construction.
            return ProviderDeliveryResult(accepted=False, error="OneSignal credentials are unavailable")
        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Key {settings.onesignal_app_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "app_id": settings.onesignal_app_id,
                    "target_channel": "push",
                    "include_subscription_ids": [subscription_id],
                    "ttl": ttl, "mutable_content": True, "ios_badgeType": "Set", "ios_badgeCount": badge_count,
                    "ios_sound": "default",
                    # If iOS bypasses its service extension, only generic copy
                    # can be shown. Private league/roster text is promoted by
                    # the native extension after its current-account check.
                    "headings": {"en": "CFFB" if private_alert else title},
                    "contents": {"en": "Open CFFB to view your alert." if private_alert else body},
                    "data": {**data, "alert_title": title, "alert_body": body} if private_alert else data,
                    # Deterministic across a retry after a crash between the
                    # provider response and the database commit.
                    "idempotency_key": idempotency_key,
                },
                timeout=10.0,
            )
        except httpx.TimeoutException:
            return ProviderDeliveryResult(accepted=False, retryable=True, error="OneSignal request timed out")
        except httpx.HTTPError:
            return ProviderDeliveryResult(accepted=False, retryable=True, error="OneSignal network request failed")

        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {}
        errors = payload.get("errors", {}) if isinstance(payload, dict) else {}
        invalid_ids = errors.get("invalid_player_ids", []) if isinstance(errors, dict) else []
        invalid_ids += errors.get("invalid_subscription_ids", []) if isinstance(errors, dict) else []
        if subscription_id in invalid_ids:
            return ProviderDeliveryResult(accepted=False, invalid_subscription_id=subscription_id, error="OneSignal subscription is invalid")
        message_id = payload.get("id") if isinstance(payload, dict) else None
        if 200 <= response.status_code < 300 and isinstance(message_id, str) and message_id:
            return ProviderDeliveryResult(accepted=True, provider_message_id=message_id)
        return ProviderDeliveryResult(
            accepted=False, retryable=response.status_code == 429 or response.status_code >= 500,
            error=f"OneSignal rejected notification (HTTP {response.status_code})",
        )


def verify_subscription_identity(subscription_id: str, external_user_id: str) -> None:
    """Check provider ownership server-side before accepting an opaque subscription ID."""
    from urllib.parse import quote
    try:
        response = httpx.get(
            f"https://api.onesignal.com/apps/{quote(settings.onesignal_app_id or '', safe='')}/subscriptions/{quote(subscription_id, safe='')}/user/identity",
            headers={"Authorization": f"Key {settings.onesignal_app_api_key}"}, timeout=10.0,
        )
        payload = response.json() if response.is_success else {}
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Push registration could not be verified. Try again.") from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise RuntimeError("Push registration could not be verified. Try again.")
    if not isinstance(payload, dict) or not isinstance(payload.get("identity"), dict) or payload["identity"].get("external_id") != external_user_id:
        raise PermissionError("subscription identity does not match")


class DisabledEmailProvider:
    def send(self, **_: object) -> ProviderDeliveryResult:
        return ProviderDeliveryResult(accepted=False, error="email delivery is disabled")


class FakeEmailProvider:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, **payload: object) -> ProviderDeliveryResult:
        self.messages.append(payload)
        return ProviderDeliveryResult(accepted=True, provider_message_id=str(payload["idempotency_key"]))


class ResendEmailProvider:
    endpoint = "https://api.resend.com/emails"

    def send(
        self,
        *,
        email: str,
        title: str,
        body: str,
        idempotency_key: str,
    ) -> ProviderDeliveryResult:
        if not settings.resend_api_key or not settings.resend_from:
            return ProviderDeliveryResult(accepted=False, error="Resend credentials are unavailable")
        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                json={"from": settings.resend_from, "to": [email], "subject": title, "text": body},
                timeout=10.0,
            )
        except httpx.TimeoutException:
            return ProviderDeliveryResult(accepted=False, retryable=True, error="Resend request timed out")
        except httpx.HTTPError:
            return ProviderDeliveryResult(accepted=False, retryable=True, error="Resend network request failed")
        if 200 <= response.status_code < 300:
            try:
                payload = response.json() if response.content else {}
            except ValueError:
                payload = {}
            message_id = payload.get("id") if isinstance(payload, dict) else None
            return ProviderDeliveryResult(accepted=True, provider_message_id=str(message_id) if message_id else None)
        return ProviderDeliveryResult(
            accepted=False,
            retryable=response.status_code == 429 or response.status_code >= 500,
            error=f"Resend rejected notification (HTTP {response.status_code})",
        )


def get_push_provider() -> PushNotificationProvider:
    if not settings.push_notifications_enabled:
        return DisabledPushProvider()
    if settings.push_provider == "fake":
        return FakePushProvider()
    return OneSignalPushProvider()


def get_email_provider() -> EmailNotificationProvider:
    if not settings.email_enabled:
        return DisabledEmailProvider()
    if settings.email_delivery_mode == "resend":
        return ResendEmailProvider()
    # Auth email remains on its existing SMTP path. Notification email is only
    # sent through the canonical Resend provider once explicitly configured.
    return DisabledEmailProvider()
