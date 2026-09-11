from __future__ import annotations

from sqlalchemy import text

from app.db.session import engine


def test_sqlite_pragmas_are_applied_on_every_connection():
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 30000
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
