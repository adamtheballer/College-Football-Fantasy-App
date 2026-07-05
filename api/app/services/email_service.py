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


class EmailService:
    def send(self, payload: EmailPayload) -> None:
        raise NotImplementedError

    def send_email_verification(self, email: str, token: str) -> None:
        link = f"{settings.ui_base_url.rstrip('/')}/verify-email?token={token}"
        self.send(
            EmailPayload(
                to_email=email,
                subject="Verify your CFB Fantasy account",
                body=f"Verify your account: {link}",
            )
        )

    def send_password_reset(self, email: str, token: str) -> None:
        link = f"{settings.ui_base_url.rstrip('/')}/password-reset/confirm?token={token}"
        self.send(
            EmailPayload(
                to_email=email,
                subject="Reset your CFB Fantasy password",
                body=f"Reset your password: {link}",
            )
        )


class ConsoleEmailService(EmailService):
    def send(self, payload: EmailPayload) -> None:
        logger.info("Auth email to %s: %s\n%s", payload.to_email, payload.subject, payload.body)


class SmtpEmailService(EmailService):
    def send(self, payload: EmailPayload) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required for SMTP email delivery")

        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = payload.to_email
        message["Subject"] = payload.subject
        message.set_content(payload.body)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:
            if settings.smtp_use_tls:
                client.starttls()
            if settings.smtp_username and settings.smtp_password:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)


def get_email_service() -> EmailService:
    if settings.email_delivery_mode.strip().lower() == "smtp":
        return SmtpEmailService()
    return ConsoleEmailService()
