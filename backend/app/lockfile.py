"""A simple advisory file lock so at most one scrape cycle runs at a time,
regardless of what triggered it. Defense in depth alongside removing the
redundant in-process scheduler (see app/main.py) — SQLite has no true
concurrent-writer support even with WAL mode's improvements, so two
overlapping scrapes (e.g. a manual `run-once` while the scheduled task's
own run is still going) could still corrupt or lose data. This doesn't
require a database migration or any new dependency, and is easy to
inspect (and delete) by hand if something ever goes wrong.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import DATA_DIR

LOCK_PATH: Path = DATA_DIR / "scrape.lock"

# A lock file older than this is assumed to be left over from a process
# that crashed or was killed without cleaning up, not a real overlap — a
# full scrape cycle normally finishes in well under an hour.
STALE_LOCK_SECONDS = 3600


class ScrapeAlreadyRunning(RuntimeError):
    pass


@contextmanager
def scrape_lock() -> Iterator[None]:
    if LOCK_PATH.exists():
        age = time.time() - LOCK_PATH.stat().st_mtime
        if age < STALE_LOCK_SECONDS:
            holder = LOCK_PATH.read_text(encoding="utf-8").strip()
            raise ScrapeAlreadyRunning(
                f"Another scrape appears to already be running (lock held by [{holder}], "
                f"{age:.0f}s ago). Refusing to start a second one against the same database. "
                f"If you're certain nothing is actually running, delete {LOCK_PATH}."
            )
        # older than STALE_LOCK_SECONDS — treat as an abandoned lock from a
        # crashed process and proceed, overwriting it below.

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(f"pid={os.getpid()} started={time.time()}", encoding="utf-8")
    try:
        yield
    finally:
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass
