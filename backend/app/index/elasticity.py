"""Lead-time (advance-purchase window) elasticity: how fares move as the
booking window shortens — the dashboard's elasticity-curve requirement.

For each advance-purchase window we report the mean/min/max of the
cheapest fare observed per route/day, plus a simple point elasticity of
fare with respect to lead time between adjacent windows:

    elasticity = (%change in price) / (%change in lead time)

A negative elasticity is the expected sign (shorter lead time -> higher
price, i.e. price falls as lead time *rises*); its magnitude is the
standard way to express how much last-minute bookings are penalised.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AP_WINDOWS
from app.db.models import FareQuote


def lead_time_curve(session: Session, route_id: int | None = None) -> list[dict]:
    query = select(FareQuote.ap_window_days, FareQuote.total_fare).where(
        FareQuote.is_outlier.is_(False),
        FareQuote.sold_out.is_(False),
        FareQuote.total_fare.is_not(None),
    )
    if route_id is not None:
        query = query.where(FareQuote.route_id == route_id)

    by_window: dict[int, list[float]] = defaultdict(list)
    for ap_days, total_fare in session.execute(query).all():
        by_window[ap_days].append(total_fare)

    curve = []
    for ap_days in AP_WINDOWS:
        values = by_window.get(ap_days, [])
        if not values:
            continue
        curve.append(
            {
                "ap_window_days": ap_days,
                "mean_fare": sum(values) / len(values),
                "min_fare": min(values),
                "max_fare": max(values),
                "sample_size": len(values),
            }
        )

    for i in range(1, len(curve)):
        prev, curr = curve[i - 1], curve[i]
        pct_price_change = (curr["mean_fare"] - prev["mean_fare"]) / prev["mean_fare"]
        pct_leadtime_change = (curr["ap_window_days"] - prev["ap_window_days"]) / prev["ap_window_days"]
        curr["elasticity_vs_prev"] = (
            pct_price_change / pct_leadtime_change if pct_leadtime_change != 0 else None
        )

    return curve
