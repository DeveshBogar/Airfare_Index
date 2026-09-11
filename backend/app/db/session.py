from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import DATA_DIR, DB_PATH
from app.db.models import Base

DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    """WAL mode lets readers (the API serving the dashboard) run concurrently
    with a writer (a scrape in progress) instead of blocking each other, and
    busy_timeout makes SQLite retry for a few seconds on a transient lock
    instead of raising `database is locked` immediately. Both are standard
    fixes for exactly the concurrent-write failures this project hit before
    (see docs/architecture.md) — cheap, well-established, and reversible."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    # SQLite does not enforce foreign keys by default even though the ORM
    # models declare them — turning this on means a bug that tries to
    # insert a FareQuote against a nonexistent route/carrier fails loudly
    # at insert time instead of silently creating orphaned data that only
    # a manual audit (see app.cli validate-data) would ever catch.
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
