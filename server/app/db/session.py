from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    return create_engine(url, **kwargs)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create missing tables only. Never drops or alters existing tables/data."""
    from app import models  # noqa: F401  (register tables)
    if settings.database_url.startswith("sqlite:///"):
        from pathlib import Path
        Path(settings.database_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
