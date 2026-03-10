from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User


def get_current_user(
    db: Session = Depends(get_db),
    x_user_token: str | None = Header(default=None),
) -> User:
    if not x_user_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth token")
    user = db.query(User).filter(User.api_token == x_user_token).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth token")
    return user
