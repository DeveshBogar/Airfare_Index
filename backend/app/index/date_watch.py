"""'Track my trip' watch: for one route and one exact travel date the
traveller actually cares about, shows every real price we've collected for
that specific date so far (grouped by how many days before departure it
was booked), which checkpoints are still pending, and - once there's
enough real history for that date - a plain verdict on the cheapest price
seen so far.

This is deliberately narrower than app.index.booking_advice, which pools
prices across every travel date a route has ever had. A specific date only
gets a real lead-time curve once several real scrape days have passed for
it (we only scrape AP_WINDOWS-days-ahead, once a day), so early on this
will often have just one or zero real points for a while.

Checkpoints with no real data yet (status "missed", "upcoming", or
"checking_today") are filled with an estimate from app.index.estimation -
the same real-factors model used for the route x window heatmap - so the
timeline never shows a bare gap. Every such cell is clearly flagged
(`is_estimated`) with its confidence and basis, and estimates never feed
into `cheapest_so_far` / `priciest_so_far` / the headline message below:
that verdict is computed from real, collected data only, exactly as
before - estimates fill in the visual timeline, they don't get to claim
being "the cheapest price we've seen."
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AP_WINDOWS
from app.db.models import FareQuote, Route
from app.index.estimation import estimate_route_window, prepare_estimation_context

MIN_POINTS_FOR_VERDICT = 2


def date_watch(session: Session, route_id: int, travel_date: dt.date, today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    travel_dt = dt.datetime.combine(travel_date, dt.time.min)
    route = session.get(Route, route_id)

    rows = session.execute(
        select(FareQuote.ap_window_days, FareQuote.total_fare, FareQuote.sold_out, FareQuote.source_id).where(
            FareQuote.route_id == route_id,
            FareQuote.travel_date == travel_dt,
            FareQuote.is_outlier.is_(False),
        )
    ).all()

    by_window: dict[int, list[float]] = {}
    sold_out_windows: set[int] = set()
    for ap_days, total_fare, sold_out, _source_id in rows:
        if sold_out or total_fare is None:
            sold_out_windows.add(ap_days)
            continue
        by_window.setdefault(ap_days, []).append(total_fare)

    mult_info, fallback_cost_per_km = prepare_estimation_context(session) if route is not None else (None, None)

    checkpoints = []
    for ap_days in sorted(AP_WINDOWS, reverse=True):
        checkpoint_scrape_date = travel_date - dt.timedelta(days=ap_days)
        fares = by_window.get(ap_days)
        if fares:
            status = "collected"
        elif ap_days in sold_out_windows:
            status = "sold_out"
        elif checkpoint_scrape_date < today:
            status = "missed"  # that lead time already passed before we ever checked
        elif checkpoint_scrape_date == today:
            status = "checking_today"
        else:
            status = "upcoming"

        checkpoint = {
            "ap_window_days": ap_days,
            "checkpoint_date": checkpoint_scrape_date,
            "status": status,
            "mean_fare": (sum(fares) / len(fares)) if fares else None,
            "min_fare": min(fares) if fares else None,
            "sample_size": len(fares) if fares else 0,
            "is_estimated": False,
            "confidence": None,
            "basis": None,
            "range_low": None,
            "range_high": None,
        }

        # sold_out is real, definitive information - never substitute a
        # made-up price for a flight we already know sold out that day.
        if not fares and status != "sold_out" and route is not None and mult_info is not None:
            est = estimate_route_window(session, route, ap_days, mult_info, fallback_cost_per_km, travel_date=travel_date)
            if est is not None:
                checkpoint["mean_fare"] = est["mean_fare"]
                checkpoint["is_estimated"] = True
                checkpoint["confidence"] = est["confidence"]
                checkpoint["basis"] = est["basis"]
                checkpoint["range_low"] = est["range_low"]
                checkpoint["range_high"] = est["range_high"]

        checkpoints.append(checkpoint)

    collected = [c for c in checkpoints if c["status"] == "collected"]

    result: dict = {
        "travel_date": travel_date,
        "checkpoints": checkpoints,
        "has_signal": len(collected) >= MIN_POINTS_FOR_VERDICT,
    }

    if not collected:
        result["message"] = "No real prices collected for this exact date yet."
        return result

    if len(collected) == 1:
        only = collected[0]
        result["message"] = (
            f"We've only seen this date priced once so far - {only['ap_window_days']} days before departure, "
            f"at {only['min_fare']:.0f}. Check back as we collect more real prices for this date."
        )
        result["cheapest_so_far"] = only
        return result

    # min_fare, not mean_fare: a checkpoint's real quotes mix every
    # SpiceJet fare class with however many carriers/re-scrapes happened
    # to run for it, so "the cheapest real price we've seen" should be a
    # literal minimum, not an average pulled up by premium fare classes.
    cheapest = min(collected, key=lambda c: c["min_fare"])
    priciest = max(collected, key=lambda c: c["min_fare"])
    gap_pct = 100 * (priciest["min_fare"] - cheapest["min_fare"]) / priciest["min_fare"]

    result["cheapest_so_far"] = cheapest
    result["priciest_so_far"] = priciest
    result["gap_pct"] = round(gap_pct, 1)
    result["message"] = (
        f"The cheapest real price we've seen for this date so far was {cheapest['min_fare']:.0f}, "
        f"booked {cheapest['ap_window_days']} days ahead - {gap_pct:.0f}% less than the priciest point we've "
        f"seen ({priciest['min_fare']:.0f}, {priciest['ap_window_days']} days ahead)."
    )
    return result
