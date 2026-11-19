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


# Columns added after the legacy schema: (table, column, SQL type). Purely additive and nullable.
ADDITIVE_COLUMNS = [
    ("found_reports", "colour", "VARCHAR(80)"),
    ("found_reports", "distinguishing_features", "TEXT"),
    ("notifications", "match_id", "INTEGER"),
    ("lost_reports", "occurred_at", "DATETIME"),
    ("found_reports", "occurred_at", "DATETIME"),
    ("match_results", "words_photo_similarity", "FLOAT"),
    ("match_results", "dismissed", "BOOLEAN NOT NULL DEFAULT 0"),
    ("recovery_requests", "proof", "TEXT"),
    ("recovery_requests", "verified_at", "DATETIME"),
    ("recovery_requests", "completed_at", "DATETIME"),
]


def init_db(bind=None) -> None:
    """Create missing tables and add missing nullable columns. Never drops/rewrites existing data."""
    from sqlalchemy import inspect, text
    from app import models  # noqa: F401  (register tables)
    bind = bind or engine
    if bind is engine and settings.database_url.startswith("sqlite:///"):
        from pathlib import Path
        Path(settings.database_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind)
    insp = inspect(bind)
    with bind.begin() as conn:
        for table, column, sql_type in ADDITIVE_COLUMNS:
            if column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
