from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import func

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.core.security import generate_token, hash_password, verify_password
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.auth import normalize_email, validate_password_strength
from collegefootballfantasy_api.app.services.auth_security import reset_failed_login_state, utcnow


def _default_username(email: str) -> str:
    return email.split("@", 1)[0][:80]


def repair_local_auth_account(*, email: str, password: str, first_name: str) -> dict[str, object]:
    normalized_email = normalize_email(email)
    validate_password_strength(password)
    now = utcnow()

    session = SessionLocal()
    try:
        user = session.query(User).filter(func.lower(User.email) == normalized_email).first()
        created = user is None
        password_changed = True

        if user is None:
            user = User(
                first_name=first_name,
                email=normalized_email,
                username=_default_username(normalized_email),
                password_hash=hash_password(password),
                api_token=generate_token(32),
                is_active=True,
                email_verified_at=now,
                password_changed_at=now,
            )
            session.add(user)
        else:
            password_changed = not verify_password(password, user.password_hash)
            if password_changed:
                user.password_hash = hash_password(password)
                user.password_changed_at = now
            user.email = normalized_email
            user.first_name = user.first_name or first_name
            user.username = user.username or _default_username(normalized_email)
            user.api_token = user.api_token or generate_token(32)
            user.is_active = True
            user.email_verified_at = user.email_verified_at or now
            reset_failed_login_state(user)

        session.commit()
        session.refresh(user)
        return {
            "user_id": user.id,
            "email": user.email,
            "created": created,
            "password_changed": password_changed,
            "verified": user.email_verified_at is not None,
            "active": user.is_active,
        }
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Repair a local development auth account by creating/verifying/unlocking it "
            "and setting the password you enter. Do not use this for production data."
        )
    )
    parser.add_argument("--email", default="emmab1167@icloud.com", help="Account email to repair.")
    parser.add_argument("--first-name", default="Emma", help="First name to use if the account must be created.")
    args = parser.parse_args()

    password = getpass.getpass("Password to set for this local account: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    result = repair_local_auth_account(email=args.email, password=password, first_name=args.first_name)
    print(
        "Repaired local auth account: "
        f"email={result['email']} user_id={result['user_id']} "
        f"created={result['created']} password_changed={result['password_changed']} "
        f"verified={result['verified']} active={result['active']}"
    )


if __name__ == "__main__":
    main()
