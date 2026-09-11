"""Route affordability: normalizes real fares against two concrete,
relatable references instead of a bare rupee figure — real distance
(cost per km) and real wages (days of a casual labourer's daily wage).

This is the problem statement's CPI-augmentation angle made literal: a
price index number means little on its own, but "this route costs 43%
more per km than that one" or "this one-way fare costs 18 days of an
average casual labourer's wages" is immediately concrete. Both
references are real, sourced government/open data (see
app.config.AIRPORT_COORDINATES and app.config.WAGE_REFERENCE) — nothing
here is estimated or fabricated.
"""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AIRPORT_COORDINATES, ROUTE_BASKET, WAGE_REFERENCE
from app.db.models import FareQuote, Route

EARTH_RADIUS_KM = 6371.0088  # IUGG mean earth radius — the standard constant for great-circle distance


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres. This is
    the direct point-to-point distance, not the actual flown distance
    (real flight paths add some distance for routing/holding/airway
    structure) — reported as such, not presented as the literal flown
    figure."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def route_distance_km(origin: str, destination: str) -> float | None:
    if origin not in AIRPORT_COORDINATES or destination not in AIRPORT_COORDINATES:
        return None
    lat1, lon1 = AIRPORT_COORDINATES[origin]
    lat2, lon2 = AIRPORT_COORDINATES[destination]
    return haversine_km(lat1, lon1, lat2, lon2)


def _representative_fare(session: Session, route_id: int) -> tuple[float, float, int] | None:
    """Mean of every real, non-outlier, non-sold-out fare currently on
    file for a route, pooled across whatever advance-purchase windows we
    have data for — not adjusted for the booking-lead-time mix, which is
    stated plainly wherever this is shown. This mean is deliberately kept
    for cost-per-km / wage-days: those are CPI-style average-cost-burden
    metrics, where a statistical mean is the methodologically right
    choice — unlike a single "the price" figure, they're not meant to be
    compared against one specific bookable fare. The real cheapest fare
    in the same pool is returned alongside for display, since that IS
    what a traveller (and any booking site) would compare against."""
    rows = session.execute(
        select(FareQuote.total_fare).where(
            FareQuote.route_id == route_id,
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()
    if not rows:
        return None
    values = [r[0] for r in rows]
    return sum(values) / len(values), min(values), len(values)


def route_affordability(session: Session, route: Route) -> dict | None:
    fare_stats = _representative_fare(session, route.id)
    if fare_stats is None:
        return None
    mean_fare, cheapest_fare, sample_size = fare_stats

    distance_km = route_distance_km(route.origin, route.destination)
    if distance_km is None or distance_km <= 0:
        return None

    cost_per_km = mean_fare / distance_km
    wage = WAGE_REFERENCE
    return {
        "route": route.display_name,
        "origin": route.origin,
        "destination": route.destination,
        "distance_km": round(distance_km, 1),
        "mean_fare": round(mean_fare, 2),
        "cheapest_fare": round(cheapest_fare, 2),
        "sample_size": sample_size,
        "cost_per_km": round(cost_per_km, 2),
        "wage_days_male_casual_labour": round(mean_fare / wage.casual_labour_daily_wage_male_inr, 1),
        "wage_days_female_casual_labour": round(mean_fare / wage.casual_labour_daily_wage_female_inr, 1),
    }


def basket_affordability(session: Session) -> dict:
    routes = session.execute(select(Route)).scalars().all()
    basket_pairs = {frozenset(p) for p in ROUTE_BASKET}
    by_pair = {frozenset([r.origin, r.destination]): r for r in routes}

    results = []
    for pair in basket_pairs:
        route = by_pair.get(pair)
        if route is None:
            continue
        row = route_affordability(session, route)
        if row is not None:
            results.append(row)

    results.sort(key=lambda r: r["cost_per_km"], reverse=True)

    cheapest_per_km = min(results, key=lambda r: r["cost_per_km"]) if results else None
    most_expensive_per_km = results[0] if results else None
    gap_pct = None
    if cheapest_per_km and most_expensive_per_km and cheapest_per_km is not most_expensive_per_km:
        gap_pct = round(
            100 * (most_expensive_per_km["cost_per_km"] - cheapest_per_km["cost_per_km"]) / cheapest_per_km["cost_per_km"],
            1,
        )

    return {
        "routes": results,
        "cheapest_per_km_route": cheapest_per_km["route"] if cheapest_per_km else None,
        "most_expensive_per_km_route": most_expensive_per_km["route"] if most_expensive_per_km else None,
        "cost_per_km_gap_pct": gap_pct,
        "wage_reference": {
            "report_label": WAGE_REFERENCE.report_label,
            "survey_period": WAGE_REFERENCE.survey_period,
            "published_date": WAGE_REFERENCE.published_date,
            "casual_labour_daily_wage_male_inr": WAGE_REFERENCE.casual_labour_daily_wage_male_inr,
            "casual_labour_daily_wage_female_inr": WAGE_REFERENCE.casual_labour_daily_wage_female_inr,
            "regular_salaried_monthly_earnings_male_inr": WAGE_REFERENCE.regular_salaried_monthly_earnings_male_inr,
            "regular_salaried_monthly_earnings_female_inr": WAGE_REFERENCE.regular_salaried_monthly_earnings_female_inr,
            "self_employed_monthly_earnings_male_inr": WAGE_REFERENCE.self_employed_monthly_earnings_male_inr,
            "self_employed_monthly_earnings_female_inr": WAGE_REFERENCE.self_employed_monthly_earnings_female_inr,
            "source_url": WAGE_REFERENCE.source_url,
            "source_note": WAGE_REFERENCE.source_note,
        },
    }
