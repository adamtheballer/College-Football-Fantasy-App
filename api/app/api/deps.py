from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import JWTError, JWTExpiredError, verify_access_token
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.domain.permissions import PermissionAction
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.access_control import (
    get_league_membership as get_access_league_membership,
    require_permission,
)


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth token")
        try:
            payload = verify_access_token(token)
        except JWTExpiredError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired access token") from exc
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid access token") from exc

        user_id_raw = payload.get("sub")
        try:
            user_id = int(user_id_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid access token") from exc

        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid access token")
        return user

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")


def get_optional_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User | None:
    if not authorization:
        return None
    return get_current_user(db, authorization)


def require_verified_user(current_user: User = Depends(get_current_user)) -> User:
    if settings.email_verification_required and current_user.email_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email verification required")
    return current_user


def require_admin_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    require_permission(
        db,
        user=current_user,
        action=PermissionAction.ADMIN_ACCESS,
        detail="admin access required",
    )
    return current_user


def get_league_or_404(db: Session, league_id: int) -> League:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return league


def get_league_membership(db: Session, league_id: int, user_id: int) -> LeagueMember | None:
    return get_access_league_membership(db, league_id, user_id)


def require_league_member(db: Session, league_id: int, current_user: User) -> LeagueMember:
    league = get_league_or_404(db, league_id)
    require_permission(
        db,
        user=current_user,
        action=PermissionAction.READ_LEAGUE,
        league=league,
        detail="league membership required",
    )
    membership = get_league_membership(db, league_id, current_user.id)
    if not membership and current_user.email.lower() in settings.configured_admin_emails:
        return LeagueMember(league_id=league_id, user_id=current_user.id, role="admin")
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="league membership required")
    return membership


def require_commissioner(db: Session, league_id: int, current_user: User) -> tuple[League, LeagueMember]:
    league = get_league_or_404(db, league_id)
    require_permission(
        db,
        user=current_user,
        action=PermissionAction.COMMISSIONER_OVERRIDE,
        league=league,
        detail="commissioner only",
    )
    membership = get_league_membership(db, league_id, current_user.id)
    if not membership:
        membership = LeagueMember(league_id=league_id, user_id=current_user.id, role="admin")
    return league, membership


def get_team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team not found")
    return team


def require_team_member(db: Session, team_id: int, current_user: User) -> Team:
    team = get_team_or_404(db, team_id)
    require_league_member(db, team.league_id, current_user)
    return team


def require_team_owner(db: Session, team_id: int, current_user: User) -> Team:
    team = require_team_member(db, team_id, current_user)
    require_permission(
        db,
        user=current_user,
        action=PermissionAction.ROSTER_MOVE,
        team=team,
        detail="team ownership required",
    )
    return team


def get_roster_entry_or_404(db: Session, roster_entry_id: int) -> RosterEntry:
    entry = db.get(RosterEntry, roster_entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")
    return entry
