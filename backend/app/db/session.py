from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, inspect
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

# Columns added to tables that already exist in deployed databases.
# create_all() creates missing *tables* but never alters existing ones, so
# without this an established data/airfare.db keeps its old shape and every
# query touching a new column fails with "no such column".
#
# This is intentionally not Alembic. Alembic earns its keep once migrations
# need ordering, data backfills or rollback; every entry here is a nullable
# or defaulted ADD COLUMN, which SQLite applies in place and which is safe to
# re-run. If a migration ever needs more than that, it needs Alembic, not a
# bigger version of this list.
_ADDITIVE_COLUMNS: list[tuple[str, str, str]] = [
    ("regulator_fare_flags", "operator_response", "VARCHAR(4096) DEFAULT ''"),
    ("regulator_fare_flags", "operator_responded_by", "VARCHAR(128) DEFAULT ''"),
    ("regulator_fare_flags", "operator_responded_at", "DATETIME"),
    # NULL default is required by SQLite for an added column carrying a
    # REFERENCES clause while foreign_keys=ON.
    ("citizen_fare_reports", "submitted_by_user_id", "INTEGER REFERENCES users(id)"),
]


def _apply_additive_columns() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table, column, ddl_type in _ADDITIVE_COLUMNS:
            if table not in existing_tables:
                continue  # create_all() already built it with the column present
            columns = {c["name"] for c in inspector.get_columns(table)}
            if column in columns:
                continue
            connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")


def init_db() -> None:
    Base.metadata.create_all(engine)
    _apply_additive_columns()


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
