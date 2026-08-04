"""One backend policy for user-generated content.

The policy deliberately targets clear abuse, spam, and unsafe links while
leaving ordinary fantasy-football banter alone.  Rejection records store a
digest and a reason code, never the blocked text itself.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.moderation_event import ModerationEvent


BLOCKED_MESSAGE = "Your message contains language that isn't allowed. Please edit it and try again."
UNSAFE_URL_MESSAGE = "That link isn't allowed. Please use a safe HTTPS link and try again."

# This is a deliberately narrow, reviewed policy dictionary.  It is kept in
# source control and exercised by tests so additions remain reviewable rather
# than relying on an opaque client-side word list.
_POLICY_TERMS: dict[str, tuple[str, ...]] = {
    "hate": ("nigger", "nigga", "faggot", "tranny", "kike", "chink", "spic", "retard"),
    "explicit_sexual": ("porn", "pornography", "nudes", "sendnudes", "onlyfans", "sexsolicitation"),
    "violent_threat": ("killyourself", "kys", "iwillkillyou", "shootyou", "doxx", "doxxing"),
    "illegal_promotion": ("buycocaine", "sellcocaine", "buyheroin", "sellheroin", "terroristrecruitment"),
    "impersonation": ("officialsupport", "adminsupport", "supportaccount"),
}
_PHRASE_TERMS = frozenset(
    {
        "sendnudes",
        "sexsolicitation",
        "killyourself",
        "iwillkillyou",
        "shootyou",
        "buycocaine",
        "sellcocaine",
        "buyheroin",
        "sellheroin",
        "terroristrecruitment",
        "officialsupport",
        "adminsupport",
        "supportaccount",
    }
)
_LEET_TRANSLATION = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_SUSPICIOUS_LINK_HOSTS = ("bit.ly", "tinyurl.com", "t.me", "discord.gg")
_REPEATED_CHARACTER = re.compile(r"(.)\1{11,}", re.IGNORECASE)
_URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s]+", re.IGNORECASE)


@dataclass(frozen=True)
class ModerationDecision:
    allowed: bool
    reason_code: str | None = None


def normalize_for_moderation(value: str) -> str:
    """Normalize case, punctuation, repeated letters, Unicode, and basic leet."""

    normalized = unicodedata.normalize("NFKC", value).casefold().translate(_LEET_TRANSLATION)
    compact = re.sub(r"[^\w]+", "", normalized, flags=re.UNICODE)
    # Preserve normal doubled letters (for example the middle of a blocked
    # term) while reducing evasive stretches such as ``baaaadword``.
    return re.sub(r"(.)\1{2,}", r"\1\1", compact)


def _collapse_repeat_runs(value: str) -> str:
    """Canonicalize doubled/repeated spelling only for policy comparisons."""

    return re.sub(r"(.)\1+", r"\1", value)


def _contains_unsafe_link(value: str) -> bool:
    for match in _URL_PATTERN.findall(value):
        candidate = match if "://" in match else f"https://{match}"
        hostname = (urlparse(candidate).hostname or "").casefold()
        if not hostname or any(hostname == host or hostname.endswith(f".{host}") for host in _SUSPICIOUS_LINK_HOSTS):
            return True
    return False


def assess_user_text(value: str) -> ModerationDecision:
    if _REPEATED_CHARACTER.search(value):
        return ModerationDecision(False, "spam_repeated_characters")
    if _contains_unsafe_link(value):
        return ModerationDecision(False, "spam_or_phishing_link")

    normalized = normalize_for_moderation(value)
    # A word is normalized independently so "spice" cannot accidentally
    # match the slur "spic", while punctuation-separated evasion such as
    # "f.a.g.g.o.t" is still reduced to the blocked term.
    normalized_words = {
        re.sub(r"(.)\1{2,}", r"\1\1", re.sub(r"[^\w]+", "", word.translate(_LEET_TRANSLATION)))
        for word in unicodedata.normalize("NFKC", value).casefold().split()
    }
    collapsed_normalized = _collapse_repeat_runs(normalized)
    collapsed_words = {_collapse_repeat_runs(word) for word in normalized_words}
    for reason_code, terms in _POLICY_TERMS.items():
        if any(
            term in normalized_words
            or normalized == term
            or (term in _PHRASE_TERMS and term in normalized)
            or (len(term) >= 5 and term in normalized)
            or _collapse_repeat_runs(term) in collapsed_words
            or (term in _PHRASE_TERMS and _collapse_repeat_runs(term) in collapsed_normalized)
            for term in terms
        ):
            return ModerationDecision(False, reason_code)
    return ModerationDecision(True)


def record_moderation_event(
    db: Session,
    *,
    actor_user_id: int | None,
    field_name: str,
    reason_code: str,
    value: str | None = None,
    league_id: int | None = None,
    metadata_json: dict | None = None,
) -> None:
    content_sha256 = hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None
    db.add(
        ModerationEvent(
            actor_user_id=actor_user_id,
            league_id=league_id,
            field_name=field_name,
            reason_code=reason_code,
            content_sha256=content_sha256,
            metadata_json=metadata_json or {},
        )
    )
    # Calls happen before the rejected submission mutates domain state.  A
    # separate commit preserves the audit event while the user request fails.
    db.commit()


def moderate_user_text(
    db: Session,
    *,
    actor_user_id: int | None,
    field_name: str,
    value: str | None,
    league_id: int | None = None,
    required: bool = False,
) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned and not required:
        return None
    if not cleaned:
        record_moderation_event(
            db,
            actor_user_id=actor_user_id,
            league_id=league_id,
            field_name=field_name,
            reason_code="empty_content",
            value=value,
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=BLOCKED_MESSAGE)

    decision = assess_user_text(cleaned)
    if not decision.allowed:
        record_moderation_event(
            db,
            actor_user_id=actor_user_id,
            league_id=league_id,
            field_name=field_name,
            reason_code=decision.reason_code or "policy_violation",
            value=cleaned,
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=BLOCKED_MESSAGE)
    return cleaned


def moderate_user_url(
    db: Session,
    *,
    actor_user_id: int | None,
    field_name: str,
    value: str | None,
    league_id: int | None = None,
) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    parsed = urlparse(cleaned)
    unsafe = parsed.scheme != "https" or not parsed.hostname or _contains_unsafe_link(cleaned)
    if unsafe:
        record_moderation_event(
            db,
            actor_user_id=actor_user_id,
            league_id=league_id,
            field_name=field_name,
            reason_code="unsafe_url",
            value=cleaned,
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=UNSAFE_URL_MESSAGE)
    return cleaned
