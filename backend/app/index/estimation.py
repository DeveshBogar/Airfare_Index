"""Fills gaps in the route x booking-window display grid with estimated
fares, clearly separated from real data at every level.

**This module never touches the index.** APIx (Laspeyres/Paasche/Fisher)
is computed exclusively from real, scraped FareQuote rows in
app.index.construct — estimates from this module are computed on demand
for display only (the heatmap grid) and are never written to the
database or fed into index construction. That separation is deliberate
and load-bearing for the project's credibility: the headline index stays
100% real, always.

Methodology — a transparent, structural model built from real factors
only, not a black-box fit (with ~600 real fare quotes spread across 20
routes and 5 windows, a generic regression would be easy to overfit and
hard to audit; this decomposition is easy to check by hand):

    estimate(route, window) = route_base(route) x window_multiplier(window)
                                x spike_adjustment(route, window)

  - route_base(route): this route's own real fares, each de-seasonalized
    by dividing out that observation's window_multiplier, then averaged —
    i.e. "what would this route's fare look like at the reference
    window, based on every real price we've actually seen for it."  If
    the route has zero real data at any window, falls back to real
    distance x the basket-wide average normalized cost-per-km (the same
    real cost-per-km computed in app.index.affordability, extended to a
    route we haven't scraped yet).
  - window_multiplier(window): real, basket-wide ratio of mean fare at
    that window vs. the most-sampled window (the stable reference) —
    this is the real lead-time effect already surfaced in the "Book
    early, pay less" chart, reused here as a factor.
  - spike_adjustment(route, window): if the travel date implied by
    `window` falls inside a known festival/wedding-season window (see
    app.config.TRAVEL_SPIKE_WINDOWS), applies that ONE festival's own
    premium — the real measured ratio once we have enough same-window
    real data on both sides, otherwise a researched, festival-specific
    surge percentage (never a generic "any festival" multiplier, since
    Diwali, Chhath, Durga Puja, wedding season and Christmas each move
    fares by a genuinely different amount). 1.0 (no adjustment) only when
    the date isn't in any spike window at all.

Every estimate carries a `confidence` tag (high/medium/low, based on how
much of it rests on this route's own real data vs. a cross-route
fallback) and an honest `range` derived from the real observed spread of
fares at that window — an approximate band, not a false-precision point
number.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from statistics import mean, pstdev

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AP_WINDOWS, ROUTE_BASKET, TravelSpikeWindow, spike_window_for_date
from app.db.models import FareQuote, Route
from app.index.affordability import route_distance_km


def _real_fares_by_window(session: Session) -> dict[int, list[float]]:
    rows = session.execute(
        select(FareQuote.ap_window_days, FareQuote.total_fare).where(
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()
    by_window: dict[int, list[float]] = defaultdict(list)
    for ap_days, fare in rows:
        by_window[ap_days].append(fare)
    return by_window


def window_multipliers(session: Session) -> dict:
    """Real, basket-wide price ratio per AP window, normalized to
    whichever window has the most real observations (the most stable
    reference point available right now)."""
    by_window = _real_fares_by_window(session)
    if not by_window:
        return {"reference_window": None, "multipliers": {}, "coefficient_of_variation": {}}

    reference_window = max(by_window, key=lambda w: len(by_window[w]))
    reference_mean = mean(by_window[reference_window])

    # A pooled, basket-wide coefficient of variation - the fallback used
    # whenever a window has too few of its own real samples to measure its
    # own spread. A single sample has a *measured* variance of exactly
    # zero, but that's not the same as *knowing* the spread is zero - it
    # just means there's nothing to measure yet, so falling back to "how
    # much do fares generally vary across the whole basket" is the honest
    # choice instead of quietly implying false precision.
    all_fares = [v for values in by_window.values() for v in values]
    all_mean = mean(all_fares) if all_fares else 0
    global_cv = (pstdev(all_fares) / all_mean) if len(all_fares) > 1 and all_mean else 0.25

    multipliers = {}
    cv = {}
    for w in AP_WINDOWS:
        values = by_window.get(w)
        if not values:
            continue
        m = mean(values)
        multipliers[w] = m / reference_mean
        cv[w] = (pstdev(values) / m) if len(values) > 1 and m else global_cv

    # a window with no real data anywhere yet: interpolate from the
    # nearest windows that do have one, rather than leaving it undefined
    known = sorted(multipliers)
    for w in AP_WINDOWS:
        if w in multipliers:
            continue
        lower = max((k for k in known if k < w), default=None)
        upper = min((k for k in known if k > w), default=None)
        if lower is not None and upper is not None:
            frac = (w - lower) / (upper - lower)
            multipliers[w] = multipliers[lower] + frac * (multipliers[upper] - multipliers[lower])
        elif lower is not None:
            multipliers[w] = multipliers[lower]
        elif upper is not None:
            multipliers[w] = multipliers[upper]
        else:
            multipliers[w] = 1.0
        cv[w] = global_cv  # an interpolated window has no real spread of its own to measure at all

    return {"reference_window": reference_window, "reference_mean_fare": reference_mean, "multipliers": multipliers, "coefficient_of_variation": cv}


def _route_normalized_base(
    session: Session, route: Route, multipliers: dict, exclude_spike_dates: bool = False
) -> tuple[float, int] | None:
    """This route's own real fares, de-seasonalized by the lead-time
    window multiplier only (never a spike adjustment - callers that want
    a spike-adjusted price apply that separately, on top). With
    `exclude_spike_dates=True`, fares whose travel date falls inside ANY
    known festival/wedding-season window are left out entirely - used for
    an "ordinary day" baseline, where a route whose only real history
    happens to be festival-dated fares must NOT have that festival
    premium silently presented back as if it were a normal-day price."""
    rows = session.execute(
        select(FareQuote.ap_window_days, FareQuote.total_fare, FareQuote.travel_date).where(
            FareQuote.route_id == route.id,
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()
    if exclude_spike_dates:
        rows = [(w, fare, travel_dt) for w, fare, travel_dt in rows if spike_window_for_date(travel_dt.date()) is None]
    if not rows:
        return None
    normalized = [fare / multipliers[w] for w, fare, _ in rows if w in multipliers and multipliers[w]]
    if not normalized:
        return None
    return mean(normalized), len(normalized)


def _basket_avg_normalized_cost_per_km(session: Session, multipliers: dict) -> float | None:
    routes = session.execute(select(Route)).scalars().all()
    per_km = []
    for route in routes:
        base = _route_normalized_base(session, route, multipliers)
        if base is None:
            continue
        distance = route_distance_km(route.origin, route.destination)
        if not distance:
            continue
        per_km.append(base[0] / distance)
    if not per_km:
        return None
    return mean(per_km)


def _festival_spike_multiplier(
    session: Session, travel_date: dt.date, origin: str, destination: str
) -> tuple[float, str | None]:
    """Real-data-first, researched-fallback spike premium for the ONE
    specific festival/wedding-season window a travel date falls in.
    Unlike a basket-pooled approach, this never mixes Diwali with Chhath
    with Christmas — each festival genuinely moves fares by a different
    amount (see app.config.TRAVEL_SPIKE_WINDOWS), so pooling them into one
    generic "festival season" multiplier would be inaccurate by
    construction.

    Prefers a real measured ratio (this window's own spike-dated fares vs.
    basket-wide non-spike fares) once there's enough real data on both
    sides to trust it. Until then, falls back to a researched surge
    percentage specific to this festival, using the high-demand tier when
    either airport on the route is one of the festival's reported
    high-pull corridors (e.g. Kolkata for Durga Puja, Patna/Gaya for
    Chhath) and the general tier otherwise. Returns (multiplier,
    explanation); explanation is None only when the date isn't in any
    spike window at all."""
    window = spike_window_for_date(travel_date)
    if window is None:
        return 1.0, None

    rows = session.execute(
        select(FareQuote.travel_date, FareQuote.total_fare).where(
            FareQuote.is_outlier.is_(False), FareQuote.sold_out.is_(False), FareQuote.total_fare.is_not(None)
        )
    ).all()
    spike_fares, baseline_fares = [], []
    for travel_dt, fare in rows:
        travel_day = travel_dt.date()
        if window.start <= travel_day <= window.end:
            spike_fares.append(fare)
        elif spike_window_for_date(travel_day) is None:
            baseline_fares.append(fare)

    if len(spike_fares) >= 4 and len(baseline_fares) >= 4:
        ratio = mean(spike_fares) / mean(baseline_fares)
        explanation = (
            f"real {window.name} premium measured from {len(spike_fares)} fare(s) in this window vs. "
            f"{len(baseline_fares)} on ordinary days"
        )
        return ratio, explanation

    return _researched_festival_surge(window, origin, destination)


def _researched_festival_surge(window: TravelSpikeWindow, origin: str, destination: str) -> tuple[float, str]:
    is_high_demand = origin in window.high_demand_airports or destination in window.high_demand_airports
    surge_pct = window.high_demand_surge_pct if is_high_demand else window.general_surge_pct
    tier = "high-demand route for this festival" if is_high_demand else "basket-wide"
    explanation = (
        f"researched {window.name} surge (+{surge_pct:.0f}%, {tier}) — not enough real data for this "
        f"window yet to measure it directly; {window.surge_source_note}"
    )
    return 1 + surge_pct / 100, explanation


def prepare_estimation_context(session: Session) -> tuple[dict, float | None]:
    """Shared setup for one-off estimates: the basket-wide window
    multipliers and (if computable) the average normalized cost-per-km
    fallback for a route with no real data of its own. Compute this once
    per request and reuse it across multiple estimate_route_window() calls
    rather than recomputing it from scratch for every cell."""
    mult_info = window_multipliers(session)
    fallback_cost_per_km = (
        _basket_avg_normalized_cost_per_km(session, mult_info["multipliers"]) if mult_info["multipliers"] else None
    )
    return mult_info, fallback_cost_per_km


def _route_base_price(
    session: Session,
    route: Route,
    multipliers: dict,
    fallback_cost_per_km: float | None,
    exclude_spike_dates: bool = False,
) -> tuple[float, str, str] | None:
    """The route's de-seasonalized base price at the reference window,
    plus a confidence tag and the (still-growable) basis string —
    shared by every estimate below the window multiplier / spike
    adjustment stage, whether or not a spike ends up applied.
    `exclude_spike_dates` is passed straight through to
    _route_normalized_base - set it when this base feeds an "ordinary
    day" estimate that must not be inflated by the route's own
    festival-dated real fares."""
    own_base = _route_normalized_base(session, route, multipliers, exclude_spike_dates=exclude_spike_dates)
    if own_base is not None:
        base_price, n = own_base
        confidence = "high" if n >= 3 else "medium"
        fare_label = "real ordinary-day fare(s)" if exclude_spike_dates else "real fare(s)"
        basis = f"this route's own {n} {fare_label}, de-seasonalized"
        return base_price, confidence, basis

    distance = route_distance_km(route.origin, route.destination)
    if distance is None or fallback_cost_per_km is None:
        return None
    base_price = distance * fallback_cost_per_km
    confidence = "low"
    basis = f"real distance ({distance:.0f} km) x the basket's average real cost per km (no data for this route yet)"
    return base_price, confidence, basis


def estimate_route_window(
    session: Session,
    route: Route,
    ap_window_days: int,
    mult_info: dict,
    fallback_cost_per_km: float | None,
    travel_date: dt.date,
) -> dict | None:
    """Estimates one (route, ap_window_days) cell for a specific travel
    date. `travel_date` is taken as given rather than derived from
    "today + ap_window_days" — the caller knows which case it's in: a
    fresh basket scan (today + window) or one exact date a traveller
    picked (fixed, with window only changing the lookback), and those are
    not the same date in general."""
    multipliers = mult_info["multipliers"]
    if ap_window_days not in multipliers:
        return None

    base = _route_base_price(session, route, multipliers, fallback_cost_per_km)
    if base is None:
        return None
    base_price, confidence, basis = base

    spike_mult, spike_explanation = _festival_spike_multiplier(session, travel_date, route.origin, route.destination)
    if spike_explanation:
        basis = f"{basis}; {spike_explanation}"

    estimate = base_price * multipliers[ap_window_days] * spike_mult
    cv = mult_info["coefficient_of_variation"].get(ap_window_days, 0.25)

    return {
        "mean_fare": round(estimate, 2),
        "range_low": round(estimate * (1 - cv), 2),
        "range_high": round(estimate * (1 + cv), 2),
        "confidence": confidence,
        "basis": basis,
        "spike_adjusted": spike_mult != 1.0,
    }


def estimate_route_baseline(
    session: Session,
    route: Route,
    ap_window_days: int,
    mult_info: dict,
    fallback_cost_per_km: float | None,
) -> dict | None:
    """Same estimate as estimate_route_window, but for an ordinary
    (non-spike) day — no festival adjustment applied, ever. Used to build
    a fair "festival price vs. ordinary price" comparison for a route
    that has no real ordinary-day fares of its own to compare against."""
    multipliers = mult_info["multipliers"]
    if ap_window_days not in multipliers:
        return None

    base = _route_base_price(session, route, multipliers, fallback_cost_per_km, exclude_spike_dates=True)
    if base is None:
        return None
    base_price, confidence, basis = base

    estimate = base_price * multipliers[ap_window_days]
    cv = mult_info["coefficient_of_variation"].get(ap_window_days, 0.25)

    return {
        "mean_fare": round(estimate, 2),
        "range_low": round(estimate * (1 - cv), 2),
        "range_high": round(estimate * (1 + cv), 2),
        "confidence": confidence,
        "basis": basis,
    }


def basket_price_grid(session: Session, today: dt.date | None = None) -> dict:
    """Every (route, AP-window) cell in the basket: the real cheapest
    fare where we have it, an estimate (clearly flagged) where we don't.
    Each estimated cell reads as "if this route/window were searched
    today" - travel_date = today + ap_window_days, same as a real scrape
    would use.

    A real cell reports the CHEAPEST real fare found, not the mean: the
    raw quotes it's built from mix every fare class SpiceJet returns
    (Saver/Flex/Max) with however many carriers/re-scrapes happened to
    run, so a mean is pulled around by how many premium-class or repeat
    quotes exist - not a genuine "typical price". The cheapest fare is
    what a traveller (and any booking site) actually compares against,
    and is a real observation either way - just the minimum of the set
    instead of its average."""
    today = today or dt.date.today()
    mult_info, fallback_cost_per_km = prepare_estimation_context(session)

    routes = session.execute(select(Route)).scalars().all()
    by_pair = {frozenset([r.origin, r.destination]): r for r in routes}

    real_rows = session.execute(
        select(Route.display_name, Route.origin, Route.destination, FareQuote.ap_window_days, FareQuote.total_fare)
        .join(Route, FareQuote.route_id == Route.id)
        .where(FareQuote.is_outlier.is_(False), FareQuote.sold_out.is_(False), FareQuote.total_fare.is_not(None))
    ).all()
    real_by_cell: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for _name, o, d, w, fare in real_rows:
        real_by_cell[(o, d, w)].append(fare)

    cells = []
    for origin, destination in ROUTE_BASKET:
        route = by_pair.get(frozenset([origin, destination]))
        display_name = route.display_name if route else f"{origin}-{destination}"
        for w in AP_WINDOWS:
            real_values = real_by_cell.get((origin, destination, w)) or real_by_cell.get((destination, origin, w))
            if real_values:
                cells.append(
                    {
                        "route": display_name,
                        "ap_window_days": w,
                        "mean_fare": round(min(real_values), 2),
                        "sample_size": len(real_values),
                        "is_estimated": False,
                        "confidence": None,
                        "basis": None,
                        "range_low": None,
                        "range_high": None,
                    }
                )
                continue

            if route is None:
                continue
            est = estimate_route_window(
                session, route, w, mult_info, fallback_cost_per_km, travel_date=today + dt.timedelta(days=w)
            )
            if est is None:
                continue
            cells.append(
                {
                    "route": display_name,
                    "ap_window_days": w,
                    "mean_fare": est["mean_fare"],
                    "sample_size": 0,
                    "is_estimated": True,
                    "confidence": est["confidence"],
                    "basis": est["basis"],
                    "range_low": est["range_low"],
                    "range_high": est["range_high"],
                }
            )

    return {
        "cells": cells,
        "reference_window_days": mult_info["reference_window"],
        "total_cells": len(ROUTE_BASKET) * len(AP_WINDOWS),
        "real_cells": sum(1 for c in cells if not c["is_estimated"]),
        "estimated_cells": sum(1 for c in cells if c["is_estimated"]),
    }
