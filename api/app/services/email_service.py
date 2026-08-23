from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from collegefootballfantasy_api.app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailPayload:
    to_email: str
    subject: str
    body: str
    html_body: str | None = None
    message_id: str | None = None


class EmailService:
    def send(self, payload: EmailPayload) -> None:
        raise NotImplementedError


class ConsoleEmailService(EmailService):
    def send(self, payload: EmailPayload) -> None:
        logger.info("Auth email queued to %s: %s", payload.to_email, payload.subject)


class DisabledEmailService(EmailService):
    """Controlled no-mail boundary for the credential-free public beta."""

    def send(self, payload: EmailPayload) -> None:
        # Deliberately do not log addresses, message bodies, access codes, or
        # password-reset tokens when mail is unavailable.
        raise RuntimeError("Email is unavailable during beta")


class SmtpEmailService(EmailService):
    def send(self, payload: EmailPayload) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required for SMTP email delivery")

        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = payload.to_email
        message["Subject"] = payload.subject
        if payload.message_id:
            message["Message-ID"] = payload.message_id
        message.set_content(payload.body)
        if payload.html_body:
            message.add_alternative(payload.html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            if settings.smtp_use_tls:
                client.starttls()
            if settings.smtp_username and settings.smtp_password:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)


def get_email_service() -> EmailService:
    if not settings.email_enabled:
        return DisabledEmailService()
    if settings.email_delivery_mode.strip().lower() == "smtp":
        return SmtpEmailService()
    return ConsoleEmailService()
