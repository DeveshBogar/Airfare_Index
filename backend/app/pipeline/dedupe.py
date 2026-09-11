"""Drops exact-duplicate raw observations produced within a single scrape
pass (e.g. a parser regex matching the same rendered flight block twice).
Does NOT dedupe across scrape runs/time — repeated same-day passes are how
we capture genuine intraday price movement, so those are kept."""
from __future__ import annotations

from app.scraper.base import RawQuote


def dedupe_raw_quotes(quotes: list[RawQuote]) -> list[RawQuote]:
    seen: set[tuple] = set()
    result: list[RawQuote] = []
    for q in quotes:
        key = (
            q.origin,
            q.destination,
            q.carrier_code,
            q.ap_window_days,
            q.travel_date,
            q.fare_class,
            q.total_fare,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(q)
    return result
