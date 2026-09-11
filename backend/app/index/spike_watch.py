"""Festival/wedding-season fare-spike watch: flags routes whose real,
scraped fares for a travel date inside a known Indian travel-demand window
(see app.config.TRAVEL_SPIKE_WINDOWS) differ from that same route's fares
on other, non-spike dates currently in the database.

This is a same-route, cross-sectional comparison against whatever real data
already exists - never a prediction, and never a claim that a spike is
happening unless the real numbers actually show one. Because the scraper
only looks AP_WINDOWS days ahead of "today", a spike window only has real
data once "today" is close enough to it; until then this module reports the
window as "on our calendar, no data yet" rather than guessing.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ROUTE_BASKET, TRAVEL_SPIKE_WINDOWS, TravelSpikeWindow, spike_window_for_date
from app.db.models import FareQuote, Route
from app.index.estimation import estimate_route_baseline, estimate_route_window, prepare_estimation_context

MIN_SAMPLES_PER_SIDE = 2  # below this a % comparison is more noise than signal


def windows_in_scraping_horizon(as_of, horizon_end) -> list[TravelSpikeWindow]:
    """Spike windows that overlap [as_of, horizon_end] - i.e. windows the
    scraper's current AP-window range could plausibly already be reaching,
    or will reach soon."""
    return [w for w in TRAVEL_SPIKE_WINDOWS if w.start <= horizon_end and w.end >= as_of]


def route_spike_signal(session: Session, route_id: int) -> dict | None:
    rows = session.execute(
        select(FareQuote.travel_date, FareQuote.total_fare).where(
            FareQuote.route_id == route_id,
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()
    if not rows:
        return None

    by_window: dict[str, list[float]] = defaultdict(list)
    baseline: list[float] = []
    window_by_key: dict[str, TravelSpikeWindow] = {}

    for travel_date, total_fare in rows:
        window = spike_window_for_date(travel_date.date())
        if window is not None:
            by_window[window.key].append(total_fare)
            window_by_key[window.key] = window
        else:
            baseline.append(total_fare)

    if not by_window or len(baseline) < MIN_SAMPLES_PER_SIDE:
        return None

    signals = []
    for key, fares in by_window.items():
        if len(fares) < MIN_SAMPLES_PER_SIDE:
            continue
        window = window_by_key[key]
        spike_mean = sum(fares) / len(fares)
        baseline_mean = sum(baseline) / len(baseline)
        pct_change = 100 * (spike_mean - baseline_mean) / baseline_mean
        signals.append(
            {
                "window_key": window.key,
                "window_name": window.name,
                "spike_mean_fare": round(spike_mean, 2),
                "baseline_mean_fare": round(baseline_mean, 2),
                "pct_change": round(pct_change, 1),
                "spike_sample_size": len(fares),
                "baseline_sample_size": len(baseline),
            }
        )

    return signals or None


def festival_route_prices(session: Session, window_key: str, today: dt.date | None = None) -> dict | None:
    """Every basket route's price for one specific festival/wedding-season
    window, AND how that compares to the same route's ordinary-day price -
    both sides independently real wherever we've collected fares for them,
    a clearly-flagged estimate from app.index.estimation otherwise (the
    same real-factors model used everywhere else in the app). Returns
    None for an unknown window_key.

    - The festival-window price prefers real fares with a travel date
      inside [window.start, window.end] for this route; otherwise an
      estimate at the basket's most-sampled AP window (its "reference"
      window), using window.start as the representative travel date so
      the estimator can apply this exact festival's own spike effect.
    - The "ordinary day" baseline prefers this route's real fares from any
      date NOT inside ANY known spike window; otherwise an estimate at
      the same reference window with no spike adjustment applied at all
      (see estimate_route_baseline) - so a route with festival-only real
      data still gets a fair, non-inflated point of comparison.
    `pct_change` is always computed once both sides resolve to a number,
    however they got there - callers should surface is_estimated /
    baseline_is_estimated so a reader can tell how much of it rests on
    real, collected prices vs. an estimate."""
    window = next((w for w in TRAVEL_SPIKE_WINDOWS if w.key == window_key), None)
    if window is None:
        return None
    today = today or dt.date.today()

    routes_by_pair = {frozenset([r.origin, r.destination]): r for r in session.execute(select(Route)).scalars().all()}

    all_rows = session.execute(
        select(Route.origin, Route.destination, FareQuote.travel_date, FareQuote.total_fare)
        .join(Route, FareQuote.route_id == Route.id)
        .where(FareQuote.is_outlier.is_(False), FareQuote.sold_out.is_(False), FareQuote.total_fare.is_not(None))
    ).all()
    spike_by_pair: dict[frozenset, list[float]] = defaultdict(list)
    baseline_by_pair: dict[frozenset, list[float]] = defaultdict(list)
    for origin, destination, travel_dt, fare in all_rows:
        day = travel_dt.date()
        pair = frozenset([origin, destination])
        if window.start <= day <= window.end:
            spike_by_pair[pair].append(fare)
        elif spike_window_for_date(day) is None:
            baseline_by_pair[pair].append(fare)

    mult_info, fallback_cost_per_km = prepare_estimation_context(session)
    reference_window = mult_info.get("reference_window")

    routes_out = []
    for origin, destination in ROUTE_BASKET:
        pair = frozenset([origin, destination])
        route = routes_by_pair.get(pair)
        display_name = route.display_name if route else f"{origin}-{destination}"

        real_spike_values = spike_by_pair.get(pair)
        if real_spike_values:
            # The cheapest real fare, not the mean - the pool mixes every
            # SpiceJet fare class with however many carriers/re-scrapes
            # landed in this window, so a mean gets pulled up by premium
            # classes in a way that doesn't match what a real booking
            # search shows. See basket_price_grid for the same reasoning.
            price = round(min(real_spike_values), 2)
            price_is_estimated = False
            price_sample_size = len(real_spike_values)
            confidence = basis = range_low = range_high = None
        elif route is not None and reference_window is not None:
            est = estimate_route_window(
                session, route, reference_window, mult_info, fallback_cost_per_km, travel_date=window.start
            )
            if est is None:
                continue
            price = est["mean_fare"]
            price_is_estimated = True
            price_sample_size = 0
            confidence, basis = est["confidence"], est["basis"]
            range_low, range_high = est["range_low"], est["range_high"]
        else:
            continue

        real_baseline_values = baseline_by_pair.get(pair)
        if real_baseline_values:
            baseline_price = round(min(real_baseline_values), 2)
            baseline_is_estimated = False
            baseline_sample_size = len(real_baseline_values)
        else:
            base_est = estimate_route_baseline(session, route, reference_window, mult_info, fallback_cost_per_km)
            baseline_price = base_est["mean_fare"] if base_est else None
            baseline_is_estimated = base_est is not None
            baseline_sample_size = 0

        pct_change = round(100 * (price - baseline_price) / baseline_price, 1) if baseline_price else None

        routes_out.append(
            {
                "route": display_name,
                "price": price,
                "is_estimated": price_is_estimated,
                "sample_size": price_sample_size,
                "confidence": confidence,
                "basis": basis,
                "range_low": range_low,
                "range_high": range_high,
                "baseline_price": baseline_price,
                "baseline_is_estimated": baseline_is_estimated,
                "baseline_sample_size": baseline_sample_size,
                "pct_change": pct_change,
            }
        )

    routes_out.sort(key=lambda r: r["price"])

    return {
        "window_key": window.key,
        "window_name": window.name,
        "start": window.start,
        "end": window.end,
        "why": window.why,
        "routes": routes_out,
    }


def basket_spike_watch(session: Session, as_of, horizon_end) -> dict:
    """Full-basket view: the festival calendar currently within (or about
    to enter) the scraper's data horizon, plus whichever routes already
    have a real, computed comparison for one of those windows."""
    routes = {(r.origin, r.destination): r for r in session.execute(select(Route)).scalars().all()}

    route_signals = []
    for origin, destination in ROUTE_BASKET:
        route = routes.get((origin, destination)) or routes.get((destination, origin))
        if route is None:
            continue
        signals = route_spike_signal(session, route.id)
        if signals:
            for s in signals:
                route_signals.append({"route": route.display_name, **s})

    route_signals.sort(key=lambda s: abs(s["pct_change"]), reverse=True)

    horizon_windows = windows_in_scraping_horizon(as_of, horizon_end)

    return {
        "as_of": as_of,
        "calendar": [
            {
                "key": w.key,
                "name": w.name,
                "start": w.start,
                "end": w.end,
                "why": w.why,
                "in_scraping_horizon": w in horizon_windows,
            }
            for w in TRAVEL_SPIKE_WINDOWS
        ],
        "route_signals": route_signals,
    }
