"""Tests for the reliability behavior added to app.scraper.runner: a
ScrapeRun row must survive (with an honest status) no matter how a cycle
ends, instead of the whole run vanishing on any uncaught exception.

Deliberately mocks async_playwright rather than launching a real browser —
a real launch works fine from a plain CLI invocation but was observed to
hang indefinitely under pytest in this environment (likely stdio handling
between Playwright's Python bindings and its Node driver subprocess
conflicting with pytest's output capturing). Tests should be fast and not
depend on browser binaries being launchable at all; the actual scraping
behavior is exercised for real via `python -m app.cli run-once`, not here.
"""
from __future__ import annotations

import pytest

from app.db.models import ScrapeRun
from app.scraper.runner import run_scrape_cycle_sync


class _FakeChromium:
    def __init__(self, on_launch=None):
        self._on_launch = on_launch

    async def launch(self, headless=True):
        if self._on_launch:
            self._on_launch()
        return _FakeBrowser()


class _FakeBrowser:
    async def close(self):
        pass


class _FakePlaywright:
    def __init__(self, on_launch=None):
        self.chromium = _FakeChromium(on_launch)


class _FakePlaywrightCM:
    def __init__(self, on_launch=None):
        self._on_launch = on_launch

    async def __aenter__(self):
        return _FakePlaywright(self._on_launch)

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_empty_cycle_completes_and_commits_a_scraperun_row(session, monkeypatch):
    # source_ids=[] means the loop body never runs, so no adapter/browser
    # interaction happens beyond launch+close — this exercises the actual
    # commit-per-step control flow end to end on the happy path.
    monkeypatch.setattr("app.scraper.runner.async_playwright", lambda: _FakePlaywrightCM())

    run = run_scrape_cycle_sync(session, source_ids=[])
    assert run.status == "ok"
    assert run.quotes_collected == 0

    stored = session.get(ScrapeRun, run.id)
    assert stored is not None
    assert stored.status == "ok"


def test_a_fatal_failure_still_leaves_a_durable_error_record(session, monkeypatch):
    def _boom():
        raise RuntimeError("simulated browser launch failure")

    monkeypatch.setattr("app.scraper.runner.async_playwright", lambda: _FakePlaywrightCM(on_launch=_boom))

    with pytest.raises(RuntimeError, match="simulated browser launch failure"):
        run_scrape_cycle_sync(session, source_ids=["spicejet"])

    # the whole point of the fix: even though the cycle blew up before
    # collecting anything, the ScrapeRun row is still there and honestly
    # marked as failed — not silently absent, as it would have been before.
    runs = session.query(ScrapeRun).order_by(ScrapeRun.id.desc()).all()
    assert len(runs) == 1
    assert runs[0].status == "error"
    assert "FATAL" in runs[0].notes
    assert "simulated browser launch failure" in runs[0].notes
