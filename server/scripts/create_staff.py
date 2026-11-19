"""Promote an existing user to staff:  python scripts/create_staff.py user@example.com
(Staff cannot self-register; the original app had no way to create one.)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.models import User  # noqa: E402

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
init_db()
with SessionLocal() as db:
    user = db.scalar(select(User).where(User.email == sys.argv[1].strip().lower()))
    if not user:
        raise SystemExit("No such user. Register the account first.")
    user.role = "staff"
    db.commit()
    print(f"{user.email} is now staff.")
