"""Signup-only address policy. Never use this to deny an existing account login."""
from __future__ import annotations

from functools import lru_cache
import logging
from time import monotonic

import dns.exception
import dns.resolver
from disposable_email_domains import blocklist
from email_validator import EmailNotValidError, EmailUndeliverableError, validate_email
from fastapi import HTTPException

from collegefootballfantasy_api.app.core.config import settings

logger = logging.getLogger(__name__)
INVALID_EMAIL = "Enter a valid email address."
DISPOSABLE_EMAIL = "Temporary email addresses cannot be used. Please use your regular email address."
UNDELIVERABLE_EMAIL = "This email domain cannot receive mail. Check your email address and try again."
DNS_UNAVAILABLE = "We could not check your email domain right now. Please try again shortly."


def _domains(value: str) -> set[str]:
    return {
        domain.strip().lower().rstrip(".").encode("idna").decode("ascii")
        for domain in value.split(",") if domain.strip()
    }


def _matches(domain: str, domains: set[str]) -> bool:
    # Match complete labels: sub.mailinator.com is disposable, but
    # notmailinator.com is a different domain.
    labels = domain.split(".")
    return any(".".join(labels[index:]) in domains for index in range(len(labels) - 1))


@lru_cache(maxsize=1)
def _dns_resolver() -> dns.resolver.Resolver:
    resolver = dns.resolver.Resolver()
    resolver.cache = dns.resolver.LRUCache(max_size=2048)
    return resolver


class _DeadlineResolver:
    """One total budget across MX and any A/AAAA/TXT fallback queries."""

    def __init__(self, seconds: float):
        self.deadline = monotonic() + seconds

    def resolve(self, *args, **kwargs):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise dns.exception.Timeout()
        return _dns_resolver().resolve(*args, lifetime=remaining, **kwargs)


def _check_mail_domain(domain: str) -> None:
    try:
        result = validate_email(
            f"signup-check@{domain}",
            check_deliverability=True,
            dns_resolver=_DeadlineResolver(settings.signup_email_dns_timeout_seconds),
        )
    except EmailUndeliverableError as exc:
        # Definitive NXDOMAIN, null MX, and no mail routing are invalid.
        # Unexpected resolver errors should ask for a retry, not label a
        # legitimate customer's address as fake or let the check be bypassed.
        if exc.__cause__ is not None and not isinstance(
            exc.__cause__, (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer)
        ):
            raise HTTPException(status_code=503, detail=DNS_UNAVAILABLE, headers={"Retry-After": "30"}) from exc
        raise HTTPException(status_code=422, detail=UNDELIVERABLE_EMAIL) from exc
    if not getattr(result, "mx", None):
        logger.warning("Signup email DNS check temporarily unavailable")
        raise HTTPException(status_code=503, detail=DNS_UNAVAILABLE, headers={"Retry-After": "30"})


def enforce_signup_email_policy(email: str) -> None:
    # Keep the existing trim/lower account key. Parser normalization is used
    # only for domain inspection so sign-in/reset lookups stay compatible.
    if len(email) > 200:
        raise HTTPException(status_code=422, detail=INVALID_EMAIL)
    try:
        address = validate_email(
            email, check_deliverability=False, strict=True,
            test_environment=settings.environment == "e2e",
        )
    except EmailNotValidError as exc:
        raise HTTPException(status_code=422, detail=INVALID_EMAIL) from exc
    domain = address.ascii_domain
    explicitly_blocked = _matches(domain, _domains(settings.signup_email_blocked_domains))
    allowed = _matches(domain, _domains(settings.signup_email_allowed_domains))
    if explicitly_blocked or (not allowed and _matches(domain, blocklist)):
        raise HTTPException(status_code=422, detail=DISPOSABLE_EMAIL)
    if settings.signup_email_check_deliverability:
        _check_mail_domain(domain)
