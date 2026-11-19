from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict, unauthorized
from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas import LoginIn, RegisterIn


def register(db: Session, data: RegisterIn) -> User:
    if db.scalar(select(User).where(User.email == data.email)):
        raise conflict("Email is already registered.", "email_taken")
    user = User(name=data.name, email=data.email, role="user", password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    return user


def authenticate(db: Session, data: LoginIn) -> User:
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise unauthorized("Invalid email or password.")
    return user
