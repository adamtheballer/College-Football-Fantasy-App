"""Seed synthetic beta-access records for the disposable real-stack E2E database.

This utility is deliberately inert unless its explicit CI-only environment
guard is present.  It stores only HMACs, never raw access codes, and is called
only after ``run_real_stack_e2e.sh`` creates a fresh Compose database.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

from sqlalchemy import select

from collegefootballfantasy_api.app.core.security import generate_token, hash_password
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.beta_access import BetaAccessCode
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.beta_access import beta_access_hmac, normalize_beta_code, normalize_beta_email


if os.environ.get("CFF_SEED_CI_BETA_ACCESS_FIXTURES") != "1":
    raise SystemExit("Refusing to seed beta fixtures outside the isolated CI E2E command.")


FIXTURES = (
    ("ci-e2e-beta-user", "ci-beta-user@example.test", "EARLY-CI1234"),
    ("ci-e2e-beta-commissioner", "ci-beta-commissioner@example.test", "EARLY-CI1235"),
    ("ci-e2e-beta-manager", "ci-beta-manager@example.test", "EARLY-CI1236"),
    ("ci-e2e-beta-trade-proposer", "ci-beta-trade-proposer@example.test", "EARLY-CI1237"),
    ("ci-e2e-beta-trade-recipient", "ci-beta-trade-recipient@example.test", "EARLY-CI1238"),
    ("ci-e2e-beta-six-manager-1", "ci-beta-six-manager-1@example.test", "EARLY-CI1239"),
    ("ci-e2e-beta-six-manager-2", "ci-beta-six-manager-2@example.test", "EARLY-CI1240"),
    ("ci-e2e-beta-six-manager-3", "ci-beta-six-manager-3@example.test", "EARLY-CI1241"),
    ("ci-e2e-beta-six-manager-4", "ci-beta-six-manager-4@example.test", "EARLY-CI1242"),
    ("ci-e2e-beta-six-manager-5", "ci-beta-six-manager-5@example.test", "EARLY-CI1243"),
    ("ci-e2e-beta-six-manager-6", "ci-beta-six-manager-6@example.test", "EARLY-CI1244"),
    ("ci-e2e-beta-six-manager-commissioner", "ci-beta-six-manager-commissioner@example.test", "EARLY-CI1245"),
)
CI_ADMIN_EMAIL = "ci-e2e-admin@example.test"
CI_ADMIN_PASSWORD = "E2E-Only-Admin-Pass-2026!"


def main() -> None:
    with SessionLocal.begin() as db:
        for source_waitlist_id, email, code in FIXTURES:
            normalized_email = normalize_beta_email(email)
            code_hmac = beta_access_hmac(normalize_beta_code(code), purpose="code")
            existing = db.scalar(
                select(BetaAccessCode).where(BetaAccessCode.source_waitlist_id == source_waitlist_id)
            )
            if existing is not None:
                if existing.email != normalized_email or existing.code_hmac != code_hmac:
                    raise RuntimeError("CI beta fixture identity does not match the isolated test registry.")
                continue
            db.add(
                BetaAccessCode(
                    source_waitlist_id=source_waitlist_id,
                    email=normalized_email,
                    code_hmac=code_hmac,
                    state="AVAILABLE",
                    source_status="READY_SENT",
                    manual_review=False,
                )
            )
        # The real-stack trade test invokes the existing admin-only due-trade
        # endpoint. This principal is created only in the fresh disposable
        # database behind the script's CI environment guard above; it is not a
        # beta-access fixture and cannot exist in a normal runtime.
        ci_admin = db.scalar(select(User).where(User.email == CI_ADMIN_EMAIL))
        if ci_admin is None:
            now = datetime.now(UTC)
            db.add(
                User(
                    first_name="CI E2E Admin",
                    email=CI_ADMIN_EMAIL,
                    username="ci-e2e-admin",
                    password_hash=hash_password(CI_ADMIN_PASSWORD),
                    api_token=generate_token(32),
                    is_admin=True,
                    email_verified_at=now,
                    password_changed_at=now,
                    last_login=now,
                )
            )
        elif not ci_admin.is_admin:
            raise RuntimeError("CI E2E admin fixture exists without admin privileges.")
    print("Seeded synthetic CI beta-access fixtures.")


if __name__ == "__main__":
    main()
