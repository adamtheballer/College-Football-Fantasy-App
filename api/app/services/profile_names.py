from datetime import datetime
from math import ceil

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.name_change import next_name_change_at
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.auth import UserProfileUpdate
from collegefootballfantasy_api.app.schemas.name_change import NameChangeEligibility
from collegefootballfantasy_api.app.services.auth_security import ensure_aware, utcnow
from collegefootballfantasy_api.app.services.content_moderation import moderate_user_text


def server_now(db: Session) -> datetime:
    # Obtain actual database time AFTER the row lock. now()/CURRENT_TIMESTAMP
    # in PostgreSQL would instead freeze time at this transaction's start.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return ensure_aware(db.scalar(select(func.clock_timestamp())))
    return utcnow()


def name_change_eligibility(user: User, now: datetime) -> NameChangeEligibility:
    now = ensure_aware(now)
    next_at = next_name_change_at(user.manager_name_changed_at)
    seconds = max(0, ceil((next_at - now).total_seconds())) if next_at else 0
    return NameChangeEligibility(account_id=user.id, current_name=user.first_name, server_time=now,
        last_successful_change_at=ensure_aware(user.manager_name_changed_at), next_eligible_at=next_at,
        remaining_wait_seconds=seconds, can_change_name=next_at is None or now >= next_at)


def update_profile(db: Session, account: User, payload: UserProfileUpdate) -> User:
    account_id, auth_version = account.id, account.auth_version
    # Serialize all profile edits and reload even if the auth dependency has
    # already populated the identity map. A second device checks the committed
    # first device's cooldown rather than its earlier authentication snapshot.
    user = db.scalar(select(User).where(User.id == account_id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active or user.auth_version != auth_version:
        raise HTTPException(status_code=401, detail="invalid auth token")
    now = server_now(db)
    if "first_name" in payload.model_fields_set:
        next_name = moderate_user_text(db, actor_user_id=user.id, field_name="manager_name", value=payload.first_name, required=True) or user.first_name
        if next_name != user.first_name:
            timing = name_change_eligibility(user, now)
            if not timing.can_change_name:
                raise HTTPException(status_code=429, detail={
                    **timing.model_dump(mode="json"), "code": "NAME_CHANGE_COOLDOWN", "field": "first_name",
                    "message": "Your manager name is still in its seven-day change window. Unsuccessful attempts do not restart the wait.",
                    "retry_at": timing.next_eligible_at.isoformat(),
                }, headers={"Retry-After": str(timing.remaining_wait_seconds)})
            user.first_name = next_name
            user.manager_name_changed_at = now
            # Preserve established generated-team label synchronization and
            # custom league/team names exactly as before.
            for team in db.scalars(select(Team).where(Team.owner_user_id == user.id)):
                team.owner_name = next_name
                if team.name.endswith("'s Team"):
                    team.name = f"{next_name}'s Team"
    if "avatar_url" in payload.model_fields_set:
        user.avatar_url = payload.avatar_url
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
