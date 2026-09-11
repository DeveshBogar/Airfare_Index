"""Orchestrates one full scrape cycle: evaluate every registered source
against the live compliance gate, then run the allowed ones across the
route basket x advance-purchase-window grid, respecting the per-domain
rate limiter and backing off on any CAPTCHA/bot-challenge detection.

This is the only place that decides whether a source actually runs live —
adapters never make that call themselves.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging

from playwright.async_api import async_playwright
from sqlalchemy.orm import Session

from app.config import AP_WINDOWS, RAW_SNAPSHOT_DIR, ROUTE_BASKET, SOURCE_REGISTRY
from app.db.models import ComplianceLog, ScrapeRun
from app.scraper.base import CaptchaDetected, RawQuote
from app.scraper.compliance import ComplianceGate
from app.scraper.ratelimit import DomainRateLimiter
from app.scraper.registry import get_adapter

logger = logging.getLogger("airfare_idex.scraper")


def _log_compliance(session: Session, result) -> None:
    for decision in result.decisions:
        session.add(
            ComplianceLog(
                source_id=result.source_id,
                domain=result.domain,
                path_checked=decision.path,
                allowed=decision.allowed,
                reason=decision.reason,
                checked_at=dt.datetime.utcnow(),
            )
        )


async def run_scrape_cycle(
    session: Session,
    source_ids: list[str] | None = None,
    route_basket: list[tuple[str, str]] | None = None,
    ap_windows: list[int] | None = None,
) -> ScrapeRun:
    """Runs one pass over (source x route x AP window), persists raw
    snapshots to disk, and returns the ScrapeRun row.

    Reliability design (this function used to be all-or-nothing: any
    uncaught exception anywhere — a browser crash, a locked database, one
    bad adapter — rolled back the *entire* cycle, including the ScrapeRun
    row itself, leaving no trace that a run was ever attempted. That was
    the most likely cause of the daily scheduled job silently producing no
    data on some days. Now:

      1. The ScrapeRun "started" row is committed immediately, on its own,
         before anything else runs — a durable record always exists.
      2. Each source's cleaned quotes are stored (and committed) right
         after that source finishes, not batched with every other source
         at the very end — one source failing doesn't lose another
         source's already-collected data.
      3. Any exception that still escapes is caught here: the run is
         marked status="error" with the real error recorded in `notes`
         and committed, then re-raised so the caller (CLI/scheduler) still
         sees the failure loudly. A failed run is now visible and
         diagnosable instead of invisible.
    """
    from app.pipeline.clean import clean_and_store  # local import: avoids a cycle at module load

    source_ids = source_ids or list(SOURCE_REGISTRY.keys())
    route_basket = route_basket or ROUTE_BASKET
    ap_windows = ap_windows or AP_WINDOWS
    today = dt.date.today()

    run = ScrapeRun(started_at=dt.datetime.utcnow(), status="running", quotes_collected=0)
    session.add(run)
    session.commit()
    run_id = run.id

    gate = ComplianceGate()
    limiter = DomainRateLimiter()
    notes: list[str] = []
    total_inserted = 0

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                for source_id in source_ids:
                    source_info = SOURCE_REGISTRY[source_id]
                    adapter = get_adapter(source_id)

                    decision = gate.evaluate(source_id, source_info.domain, adapter.compliance_paths)
                    _log_compliance(session, decision)
                    session.commit()

                    if not decision.allowed:
                        notes.append(f"{source_id}: SKIPPED — {decision.reason}")
                        logger.info("skipping %s: %s", source_id, decision.reason)
                        continue

                    source_raw: list[RawQuote] = []
                    captcha_hit = False
                    try:
                        context = await browser.new_context(user_agent=adapter.random_user_agent())
                        page = await context.new_page()

                        for origin, destination in route_basket:
                            if captcha_hit:
                                break
                            for ap_days in ap_windows:
                                travel_date = today + dt.timedelta(days=ap_days)
                                await limiter.wait(source_info.domain)
                                try:
                                    quotes = await adapter.collect(
                                        page, origin, destination, travel_date, ap_days, today
                                    )
                                    source_raw.extend(quotes)
                                except CaptchaDetected as exc:
                                    logger.warning("captcha detected, backing off %s: %s", source_id, exc)
                                    notes.append(f"{source_id}: backed off after CAPTCHA on {origin}-{destination}")
                                    captcha_hit = True
                                    break
                                except Exception as exc:  # noqa: BLE001 - one bad route shouldn't kill the source
                                    logger.exception("adapter error for %s %s-%s", source_id, origin, destination)
                                    notes.append(f"{source_id}: error on {origin}-{destination}: {exc}")

                        await context.close()
                    except Exception as exc:  # noqa: BLE001 - one bad source shouldn't kill the cycle
                        logger.exception("source %s failed entirely", source_id)
                        notes.append(f"{source_id}: source-level failure: {exc}")

                    for q in source_raw:
                        q.source_id = source_id

                    if source_raw:
                        snapshot_path = _write_raw_snapshot(run_id, source_id, source_raw)
                        for q in source_raw:
                            q.raw_snapshot_path = str(snapshot_path)
                        inserted = clean_and_store(session, run_id, source_raw)
                        total_inserted += inserted
                        notes.append(
                            f"{source_id}: collected {len(source_raw)} raw observations, stored {inserted}"
                        )
                    else:
                        notes.append(f"{source_id}: collected 0 raw observations")
            finally:
                await browser.close()
    except Exception as exc:
        logger.exception("scrape cycle %s failed", run_id)
        session.rollback()
        run = session.get(ScrapeRun, run_id)
        run.finished_at = dt.datetime.utcnow()
        run.status = "error"
        run.quotes_collected = total_inserted
        run.notes = ("\n".join(notes) + f"\nFATAL: {exc}").strip()[:1024]
        session.commit()
        raise

    run = session.get(ScrapeRun, run_id)
    run.finished_at = dt.datetime.utcnow()
    run.status = "ok"
    run.quotes_collected = total_inserted
    run.notes = "\n".join(notes)[:1024]
    session.commit()
    return run


def _write_raw_snapshot(run_id: int, source_id: str, quotes: list[RawQuote]) -> "Path":
    from pathlib import Path

    RAW_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_SNAPSHOT_DIR / f"run{run_id}_{source_id}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for q in quotes:
            row = {
                "origin": q.origin,
                "destination": q.destination,
                "carrier_code": q.carrier_code,
                "ap_window_days": q.ap_window_days,
                "search_date": q.search_date.isoformat(),
                "travel_date": q.travel_date.isoformat(),
                "fare_class": q.fare_class,
                "total_fare": q.total_fare,
                "base_fare": q.base_fare,
                "taxes_fees": q.taxes_fees,
                "sold_out": q.sold_out,
            }
            fh.write(json.dumps(row) + "\n")
    return path


def run_scrape_cycle_sync(session: Session, **kwargs) -> ScrapeRun:
    return asyncio.run(run_scrape_cycle(session, **kwargs))
