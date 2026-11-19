"""Development/testing convenience: make sure the three shared demo accounts exist so the login page's quick-login
buttons work on any fresh database. Controlled by DEMO_ACCOUNTS (default on; set DEMO_ACCOUNTS=0 for a real deployment).

Only creates missing accounts. It never changes the password or role of an account that already exists."""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User

log = logging.getLogger("findback")

DEMO_PASSWORD = "Demo12345!"
DEMO_ACCOUNTS = [
    ("Olivia Owner", "owner@demo.test", "user"),
    ("Finn Finder", "finder@demo.test", "user"),
    ("Sam Staff", "staff@demo.test", "staff"),
]


def seed_demo_accounts(db: Session) -> int:
    made = 0
    for name, email, role in DEMO_ACCOUNTS:
        if db.scalar(select(User).where(User.email == email)):
            continue
        db.add(User(name=name, email=email, role=role, password_hash=hash_password(DEMO_PASSWORD)))
        made += 1
    if made:
        db.commit()
        log.warning("Demo accounts created (%d). Disable with DEMO_ACCOUNTS=0 outside development.", made)
    return made
