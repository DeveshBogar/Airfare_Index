"""Real day-by-day price history for one route, built entirely from
scraped FareQuote rows grouped by the calendar day we actually searched.

This is the historical record itself - unlike app.index.estimation (which
fills display gaps with a modeled value), every point here is a real,
collected price with nothing backfilled or interpolated. A route with
only a few real scrape days reports honestly as having only a few real
scrape days; the chart grows one real point at a time as scraping keeps
running, exactly like the rest of this project's "Days of history" KPI.

`typical_low`/`typical_high` is a P20/P80 band over the route's daily
cheapest-fare series (the same "least expensive flights usually cost
between X-Y" framing consumer fare trackers use) - with few real days
this is necessarily a small-sample estimate, which `days_of_history`
makes visible to the caller rather than presenting false precision.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FareQuote, Route


def _percentile(sorted_values: list[float], p: float) -> float:
    """Nearest-rank percentile - simple and honest for the small sample
    sizes this function actually sees (a handful of real scrape days),
    where a fancier interpolated percentile would just be false precision."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = round(p * (len(sorted_values) - 1))
    idx = max(0, min(len(sorted_values) - 1, idx))
    return sorted_values[idx]


def route_price_history(session: Session, route_id: int) -> dict | None:
    route = session.get(Route, route_id)
    if route is None:
        return None

    rows = session.execute(
        select(FareQuote.search_date, FareQuote.total_fare).where(
            FareQuote.route_id == route_id,
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()

    by_day: dict = defaultdict(list)
    for search_dt, fare in rows:
        by_day[search_dt.date()].append(fare)

    points = [
        {
            "search_date": day,
            "cheapest_fare": round(min(fares), 2),
            "mean_fare": round(mean(fares), 2),
            "sample_size": len(fares),
        }
        for day, fares in sorted(by_day.items())
    ]

    cheapest_series = sorted(p["cheapest_fare"] for p in points)
    if cheapest_series:
        typical_low = round(_percentile(cheapest_series, 0.2), 2)
        typical_high = round(_percentile(cheapest_series, 0.8), 2)
        lowest_seen = cheapest_series[0]
        highest_seen = cheapest_series[-1]
    else:
        typical_low = typical_high = lowest_seen = highest_seen = None

    latest = points[-1] if points else None

    return {
        "route": route.display_name,
        "days_of_history": len(points),
        "points": points,
        "typical_low": typical_low,
        "typical_high": typical_high,
        "lowest_seen": lowest_seen,
        "highest_seen": highest_seen,
        "latest_cheapest_fare": latest["cheapest_fare"] if latest else None,
        "latest_search_date": latest["search_date"] if latest else None,
    }
