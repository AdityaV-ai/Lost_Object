from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import forbidden, unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False, description="Token from POST /api/v1/auth/login")
DB = Annotated[Session, Depends(get_db)]


def get_current_user(db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]) -> User:
    if creds is None:
        raise unauthorized()
    user_id = decode_access_token(creds.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise unauthorized("Invalid or expired token.")
    return user


def require_staff(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "staff":
        raise forbidden("Staff only.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
StaffUser = Annotated[User, Depends(require_staff)]
