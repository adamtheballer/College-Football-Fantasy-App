from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.security import JWTError, JWTExpiredError, verify_access_token
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User


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


def get_league_or_404(db: Session, league_id: int) -> League:
    league = db.get(League, league_id)
    if not league:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league not found")
    return league


def get_league_membership(db: Session, league_id: int, user_id: int) -> LeagueMember | None:
    return (
        db.query(LeagueMember)
        .filter(LeagueMember.league_id == league_id, LeagueMember.user_id == user_id)
        .first()
    )


def require_league_member(db: Session, league_id: int, current_user: User) -> LeagueMember:
    membership = get_league_membership(db, league_id, current_user.id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="league membership required")
    return membership


def require_commissioner(db: Session, league_id: int, current_user: User) -> tuple[League, LeagueMember]:
    league = get_league_or_404(db, league_id)
    membership = require_league_member(db, league_id, current_user)
    if league.commissioner_user_id != current_user.id and membership.role != "commissioner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="commissioner only")
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
    if team.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="team ownership required")
    return team


def get_roster_entry_or_404(db: Session, roster_entry_id: int) -> RosterEntry:
    entry = db.get(RosterEntry, roster_entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="roster entry not found")
    return entry
