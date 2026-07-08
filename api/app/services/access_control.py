from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.permissions import PermissionContext, can as can_action
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User


def is_admin_user(user: User | None) -> bool:
    if not user:
        return False
    admin_emails = settings.configured_admin_emails
    return bool(admin_emails and user.email.lower() in admin_emails)


def get_league_membership(db: Session, league_id: int, user_id: int) -> LeagueMember | None:
    return (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )


def build_permission_context(
    db: Session,
    *,
    user: User | None,
    league: League | None = None,
    team: Team | None = None,
) -> PermissionContext:
    if not user or not user.is_active:
        return PermissionContext(authenticated=False, verified=False)

    target_league_id = league.id if league is not None else team.league_id if team is not None else None
    membership = get_league_membership(db, target_league_id, user.id) if target_league_id is not None else None
    is_commissioner = False
    if target_league_id is not None:
        target_league = league if league is not None else db.get(League, target_league_id)
        commissioner_user_id = target_league.commissioner_user_id if target_league is not None else None
        is_commissioner = commissioner_user_id == user.id or bool(membership and membership.role == "commissioner")

    return PermissionContext(
        authenticated=True,
        verified=user.email_verified_at is not None,
        admin=is_admin_user(user),
        league_member=membership is not None,
        commissioner=is_commissioner,
        team_owner=bool(team is not None and team.owner_user_id == user.id),
    )


def can(
    db: Session,
    *,
    user: User | None,
    action: str,
    league: League | None = None,
    team: Team | None = None,
) -> bool:
    return can_action(build_permission_context(db, user=user, league=league, team=team), action)


def require_permission(
    db: Session,
    *,
    user: User | None,
    action: str,
    league: League | None = None,
    team: Team | None = None,
    detail: str = "permission denied",
) -> PermissionContext:
    context = build_permission_context(db, user=user, league=league, team=team)
    if not can_action(context, action):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return context
