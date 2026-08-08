#!/usr/bin/env python3
"""Safely import a beta waitlist export without ever retaining raw access codes.

The command is deliberately idempotent and defaults to a dry run. Its reports
contain aggregate statuses only so an operator can review production readiness
without printing e-mail addresses or credentials into a terminal, CI log, or
checked-in artifact.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.beta_access import BetaAccessAuditEvent, BetaAccessCode
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.auth_security import utcnow
from collegefootballfantasy_api.app.services.beta_access import (
    AUDIT_HMAC_REKEYED,
    AUDIT_IMPORTED,
    AUDIT_IMPORT_REJECTED,
    beta_access_hmac,
    normalize_beta_code,
    normalize_beta_email,
)

EXPECTED_COLUMNS = {
    "id",
    "email",
    "status",
    "discount_percent",
    "access_code_generated_at",
    "access_code_email_status",
    "access_code_email_sent_at",
    "access_code_email_provider_id",
    "access_code_email_attempt_count",
    "access_code_email_last_error",
}
CODE_COLUMNS = ("discount_code", "access_code", "early_access_code", "code")
RAW_CODE_IN_TEXT = re.compile(r"EARLY-[A-Z0-9]{6}", re.IGNORECASE)
RECONCILIATION_CATEGORIES = (
    "MATCHED", "NEEDS_HMAC_RECONCILIATION", "REDEEMED_PRESERVE",
    "RESERVED_ACTIVE", "RESERVED_EXPIRED", "MISSING_PRODUCTION_ROW",
    "DUPLICATE_PRODUCTION_ROW", "CONFLICT", "INVALID_SOURCE",
    "SUPPRESSED", "PENDING_NO_CODE",
)
@dataclass(frozen=True)
class ParsedRow:
    source_id: str | None
    email: str | None
    code: str | None
    status: str
    source_waitlist_status: str | None
    manual_review: bool
    discount_percent: int | None
    generated_at: datetime | None
    email_status: str | None
    email_sent_at: datetime | None
    provider_id: str | None
    email_attempt_count: int | None
    email_last_error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import an approved beta waitlist export safely.")
    parser.add_argument("--source", type=Path, help="Semicolon-delimited waitlist CSV export.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate source rows without writing (default).")
    mode.add_argument("--apply", action="store_true", help="Persist safe READY_SENT rows and review states.")
    mode.add_argument("--verify-only", action="store_true", help="Verify the imported registry without reading source rows.")
    parser.add_argument(
        "--rekey-code-hmac",
        action="store_true",
        help=(
            "With an approved source export, rotate only the stored HMACs for matching, "
            "available READY_SENT records after a beta-access secret rotation."
        ),
    )
    parser.add_argument("--report-path", type=Path, help="Optional aggregate-only JSON report path.")
    return parser.parse_args()


def parse_datetime(value: str | None) -> datetime | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_optional_int(value: str | None) -> int | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def redact_delivery_error(value: str | None) -> str | None:
    """Preserve provider diagnostics without turning them into a code store."""
    normalized = (value or "").strip()
    if not normalized:
        return None
    return RAW_CODE_IN_TEXT.sub("[REDACTED_ACCESS_CODE]", normalized)


def source_status(row: dict[str, str], *, email: str | None, code: str | None) -> tuple[str, bool]:
    if not email:
        return "INVALID_EMAIL", True
    if not code:
        return "INVALID_CODE", True
    delivery = (row.get("access_code_email_status") or "").strip().lower()
    if delivery == "sent":
        return "READY_SENT", False
    if delivery in {"skipped", "suppressed", "bounced", "failed"}:
        return "SKIPPED_SUPPRESSED", True
    return "READY_NOT_CONFIRMED", True


def parse_source(source: Path) -> tuple[list[ParsedRow], Counter[str]]:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        headers = set(reader.fieldnames or [])
        missing = EXPECTED_COLUMNS - headers
        code_column = next((candidate for candidate in CODE_COLUMNS if candidate in headers), None)
        if missing or not code_column:
            details = []
            if missing:
                details.append("missing required non-secret columns")
            if not code_column:
                details.append("missing access-code column")
            raise ValueError(
                f"Unsupported waitlist export ({'; '.join(details)}). "
                "No source values were printed."
            )

        raw_rows = list(reader)
        normalized_rows: list[tuple[dict[str, str], str | None, str | None, str | None]] = []
        email_counts: Counter[str] = Counter()
        code_counts: Counter[str] = Counter()
        source_id_counts: Counter[str] = Counter()
        for row in raw_rows:
            source_id = (row.get("id") or "").strip() or None
            try:
                email = normalize_beta_email(row.get("email") or "")
            except ValueError:
                email = None
            try:
                code = normalize_beta_code(row.get(code_column) or "")
            except ValueError:
                code = None
            normalized_rows.append((row, source_id, email, code))
            if source_id:
                source_id_counts[source_id] += 1
            if email:
                email_counts[email] += 1
            if code:
                code_counts[code] += 1

        rows: list[ParsedRow] = []
        status_counts: Counter[str] = Counter()
        for row, source_id, email, code in normalized_rows:
            status, manual_review = source_status(row, email=email, code=code)
            if not source_id or source_id_counts[source_id] > 1:
                status, manual_review = "MANUAL_REVIEW", True
            elif email and email_counts[email] > 1:
                status, manual_review = "DUPLICATE_EMAIL", True
            elif code and code_counts[code] > 1:
                status, manual_review = "DUPLICATE_CODE", True
            status_counts[status] += 1
            rows.append(
                ParsedRow(
                    source_id=source_id,
                    email=email,
                    code=code,
                    status=status,
                    source_waitlist_status=(row.get("status") or "").strip() or None,
                    manual_review=manual_review,
                    discount_percent=parse_optional_int(row.get("discount_percent")),
                    generated_at=parse_datetime(row.get("access_code_generated_at")),
                    email_status=(row.get("access_code_email_status") or "").strip() or None,
                    email_sent_at=parse_datetime(row.get("access_code_email_sent_at")),
                    provider_id=(row.get("access_code_email_provider_id") or "").strip() or None,
                    email_attempt_count=parse_optional_int(row.get("access_code_email_attempt_count")),
                    email_last_error=(row.get("access_code_email_last_error") or "").strip() or None,
                )
            )
    return rows, status_counts


def reconciliation_report(rows: list[ParsedRow]) -> tuple[Counter[str], list[dict[str, str]]]:
    """Classify source rows without mutating production state or emitting codes."""
    outcomes = Counter({category: 0 for category in RECONCILIATION_CATEGORIES})
    reviews: list[dict[str, str]] = []
    now = utcnow()
    with SessionLocal() as db:
        for row in rows:
            def classify(category: str, reason: str | None = None) -> None:
                outcomes[category] += 1
                if reason and row.email:
                    reviews.append({"email": row.email, "category": category, "reason": reason})

            if row.status == "SKIPPED_SUPPRESSED":
                classify("SUPPRESSED")
                continue
            if not row.code:
                classify("PENDING_NO_CODE" if row.email else "INVALID_SOURCE", "missing usable source code")
                continue
            if row.status != "READY_SENT" or not row.email or row.manual_review:
                classify("INVALID_SOURCE", "source row is not an unambiguous READY_SENT invitation")
                continue

            beta_rows = db.query(BetaAccessCode).filter(BetaAccessCode.email == row.email).all()
            if len(beta_rows) == 0:
                classify("MISSING_PRODUCTION_ROW")
                continue
            if len(beta_rows) > 1:
                classify("DUPLICATE_PRODUCTION_ROW", "multiple production rows share the normalized email")
                continue
            beta = beta_rows[0]
            users = db.query(User).filter(User.email == row.email).all()
            expected_hmac = beta_access_hmac(row.code, purpose="code")
            if len(users) > 1:
                classify("CONFLICT", "multiple users share the normalized email")
                continue
            user = users[0] if users else None
            if beta.state == "REDEEMED":
                if not user or beta.redeemed_user_id != user.id or user.beta_access_granted_at is None:
                    classify("CONFLICT", "redeemed beta row is not linked to an entitled matching user")
                else:
                    classify("REDEEMED_PRESERVE")
                continue
            if beta.state == "RESERVED":
                if beta.reservation_expires_at is None:
                    classify("CONFLICT", "reserved beta row has no expiration")
                elif beta.reservation_expires_at > now:
                    classify("RESERVED_ACTIVE")
                else:
                    classify("RESERVED_EXPIRED")
                continue
            if user and user.beta_access_granted_at is not None:
                classify("CONFLICT", "unredeemed beta row conflicts with an entitled user")
                continue
            if beta.manual_review or beta.state != "AVAILABLE" or beta.source_status != "READY_SENT":
                classify("CONFLICT", "production beta metadata is not eligible for automatic reconciliation")
                continue
            if beta.code_hmac == expected_hmac:
                classify("MATCHED")
            else:
                classify("NEEDS_HMAC_RECONCILIATION")
    return outcomes, reviews


def apply_rows(rows: list[ParsedRow], *, apply: bool, rekey_code_hmac: bool = False) -> Counter[str]:
    outcomes: Counter[str] = Counter()
    with SessionLocal() as db:
        for row in rows:
            if not row.email or not row.code:
                outcomes[row.status] += 1
                if apply:
                    db.add(BetaAccessAuditEvent(action=AUDIT_IMPORT_REJECTED, created_at=utcnow()))
                continue
            code_hmac = beta_access_hmac(row.code, purpose="code")
            existing_by_source = (
                db.query(BetaAccessCode)
                .filter(BetaAccessCode.source_waitlist_id == row.source_id)
                .one_or_none()
                if row.source_id
                else None
            )
            existing_by_email = db.query(BetaAccessCode).filter(BetaAccessCode.email == row.email).one_or_none()
            existing_by_code = db.query(BetaAccessCode).filter(BetaAccessCode.code_hmac == code_hmac).one_or_none()

            if existing_by_source and existing_by_source.email != row.email:
                outcomes["MANUAL_REVIEW"] += 1
                if apply:
                    db.add(BetaAccessAuditEvent(action=AUDIT_IMPORT_REJECTED, created_at=utcnow()))
                continue
            if existing_by_email and existing_by_email is not existing_by_source:
                outcomes["DUPLICATE_EMAIL"] += 1
                if apply:
                    db.add(BetaAccessAuditEvent(action=AUDIT_IMPORT_REJECTED, created_at=utcnow()))
                continue
            if existing_by_code and existing_by_code is not existing_by_source:
                outcomes["DUPLICATE_CODE"] += 1
                if apply:
                    db.add(BetaAccessAuditEvent(action=AUDIT_IMPORT_REJECTED, created_at=utcnow()))
                continue
            if existing_by_source:
                if existing_by_source.code_hmac != code_hmac:
                    can_rekey = (
                        rekey_code_hmac
                        and existing_by_source.state == "AVAILABLE"
                        and existing_by_source.source_status == "READY_SENT"
                        and not existing_by_source.manual_review
                        and row.status == "READY_SENT"
                        and not row.manual_review
                    )
                    if not can_rekey:
                        outcomes["MANUAL_REVIEW"] += 1
                        if apply:
                            db.add(BetaAccessAuditEvent(action=AUDIT_IMPORT_REJECTED, created_at=utcnow()))
                        continue
                    if apply:
                        existing_by_source.code_hmac = code_hmac
                        db.add(
                            BetaAccessAuditEvent(
                                beta_access_code_id=existing_by_source.id,
                                action=AUDIT_HMAC_REKEYED,
                                created_at=utcnow(),
                            )
                        )
                    outcomes["REKEYED" if apply else "WOULD_REKEY"] += 1
                    continue
                outcomes["ALREADY_REDEEMED" if existing_by_source.state == "REDEEMED" else "ALREADY_IMPORTED"] += 1
                continue

            outcomes[row.status] += 1
            if not apply:
                continue
            imported = BetaAccessCode(
                source_waitlist_id=row.source_id,
                email=row.email,
                code_hmac=code_hmac,
                state="AVAILABLE",
                source_status=row.status,
                source_waitlist_status=row.source_waitlist_status,
                manual_review=row.manual_review,
                discount_percent=row.discount_percent,
                access_code_generated_at=row.generated_at,
                email_delivery_status=row.email_status,
                email_delivery_sent_at=row.email_sent_at,
                email_delivery_provider_id=row.provider_id,
                email_delivery_attempt_count=row.email_attempt_count,
                # Preserve the operator-facing delivery outcome while ensuring
                # a provider error can never become a raw access-code store.
                email_delivery_last_error=redact_delivery_error(row.email_last_error),
            )
            db.add(imported)
            db.flush()
            db.add(BetaAccessAuditEvent(beta_access_code_id=imported.id, action=AUDIT_IMPORTED, created_at=utcnow()))
        if apply:
            db.commit()
        else:
            db.rollback()
    return outcomes


def verify_registry() -> dict[str, object]:
    with SessionLocal() as db:
        records = db.query(BetaAccessCode).all()
        states = Counter(record.state for record in records)
        unsafe_records = sum(
            1
            for record in records
            if record.source_status != "READY_SENT" and not record.manual_review
        )
        return {
            "registry_records": len(records),
            "registry_states": dict(sorted(states.items())),
            "unsafe_non_ready_records": unsafe_records,
            "ready_sent_records": sum(1 for record in records if record.source_status == "READY_SENT"),
            "manual_review_records": sum(1 for record in records if record.manual_review),
        }


def main() -> int:
    args = parse_args()
    ensure_models_registered()
    if args.rekey_code_hmac and args.verify_only:
        raise ValueError("--rekey-code-hmac requires --source and cannot be used with --verify-only")
    if args.verify_only:
        report: dict[str, object] = {"mode": "verify_only", **verify_registry()}
        exit_code = 1 if report["unsafe_non_ready_records"] else 0
    else:
        if args.source is None:
            raise ValueError("--source is required for --dry-run and --apply")
        if args.apply:
            raise ValueError("--apply is disabled for reconciliation; obtain explicit owner approval and use a reviewed transactional apply command")
        rows, source_counts = parse_source(args.source.expanduser())
        outcomes, manual_review = reconciliation_report(rows)
        report = {
            "mode": "dry_run",
            "rekey_code_hmac": args.rekey_code_hmac,
            "source_row_count": len(rows),
            "source_status_counts": dict(sorted(source_counts.items())),
            "outcome_counts": dict(sorted(outcomes.items())),
            "manual_review": manual_review,
            "raw_credentials_emitted": False,
        }
        exit_code = 0
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    print(payload)
    if args.report_path:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(payload + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
