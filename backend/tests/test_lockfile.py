from __future__ import annotations

import time

import pytest

from app import lockfile
from app.lockfile import ScrapeAlreadyRunning, scrape_lock


@pytest.fixture()
def isolated_lock(tmp_path, monkeypatch):
    path = tmp_path / "scrape.lock"
    monkeypatch.setattr(lockfile, "LOCK_PATH", path)
    return path


def test_lock_is_created_while_held_and_removed_after(isolated_lock):
    assert not isolated_lock.exists()
    with scrape_lock():
        assert isolated_lock.exists()
    assert not isolated_lock.exists()


def test_lock_is_removed_even_if_the_body_raises(isolated_lock):
    with pytest.raises(ValueError):
        with scrape_lock():
            raise ValueError("simulated failure inside the locked section")
    assert not isolated_lock.exists()


def test_second_concurrent_attempt_is_refused(isolated_lock):
    with scrape_lock():
        with pytest.raises(ScrapeAlreadyRunning):
            with scrape_lock():
                pass  # pragma: no cover - should never be reached


def test_a_stale_lock_is_ignored_and_overwritten(isolated_lock, monkeypatch):
    isolated_lock.write_text("pid=99999 started=0", encoding="utf-8")
    old_time = time.time() - lockfile.STALE_LOCK_SECONDS - 60
    import os

    os.utime(isolated_lock, (old_time, old_time))

    # should NOT raise, since the existing lock is older than the stale threshold
    with scrape_lock():
        assert isolated_lock.exists()
    assert not isolated_lock.exists()
