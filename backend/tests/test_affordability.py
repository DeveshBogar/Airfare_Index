from __future__ import annotations

import datetime as dt
import math

from app.config import AIRPORT_COORDINATES, ROUTE_BASKET
from app.db.models import Carrier, FareQuote, Route
from app.index.affordability import basket_affordability, haversine_km, route_affordability, route_distance_km


def test_haversine_km_same_point_is_zero():
    assert haversine_km(28.5, 77.1, 28.5, 77.1) == 0.0


def test_haversine_km_matches_known_real_distance_del_bom():
    # real-world DEL-BOM flight distance is ~1150km; great-circle should
    # be close to but slightly under that (no real flight path is a
    # perfect straight line)
    km = haversine_km(28.55563, 77.09519, 19.088699, 72.867897)
    assert 1100 < km < 1160


def test_route_distance_km_uses_real_config_coordinates():
    km = route_distance_km("DEL", "BOM")
    assert km is not None
    assert 1100 < km < 1160


def test_route_distance_km_returns_none_for_unknown_airport():
    assert route_distance_km("DEL", "ZZZ") is None


def test_every_route_basket_airport_has_real_coordinates():
    # this would have caught a typo'd/missing IATA code before it silently
    # broke every affordability calculation touching that airport
    airports_in_basket = {code for pair in ROUTE_BASKET for code in pair}
    missing = airports_in_basket - set(AIRPORT_COORDINATES)
    assert missing == set()


def _seed_route(session, origin="DEL", destination="BOM"):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    if session.get(Carrier, "SG") is None:
        session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    return route


def _add_quote(session, route, total_fare, ap_days=7):
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=ap_days,
            search_date=dt.datetime(2026, 9, 4),
            travel_date=dt.datetime(2026, 9, 11),
            fare_class="economy",
            total_fare=total_fare,
            is_outlier=False,
            sold_out=False,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_route_affordability_computes_real_ratios(session):
    route = _seed_route(session, "DEL", "BOM")
    _add_quote(session, route, 8000)
    _add_quote(session, route, 9000)

    result = route_affordability(session, route)
    assert result is not None
    assert result["mean_fare"] == 8500
    # the real cheapest of the two, not the mean - what "Cheapest fare" is
    # actually shown/linked for on the Affordability panel
    assert result["cheapest_fare"] == 8000
    assert result["sample_size"] == 2
    assert 1100 < result["distance_km"] < 1160
    # cost_per_km should be mean_fare / distance, computed independently here
    expected_cost_per_km = round(8500 / result["distance_km"], 2)
    assert abs(result["cost_per_km"] - expected_cost_per_km) < 0.01
    # wage_days = fare / daily wage - male casual labour wage is 455 INR (PLFS 2025)
    assert abs(result["wage_days_male_casual_labour"] - round(8500 / 455.0, 1)) < 0.01


def test_route_affordability_none_without_data(session):
    route = _seed_route(session, "DEL", "BOM")
    assert route_affordability(session, route) is None


def test_basket_affordability_ranks_routes_and_reports_gap(session):
    cheap_route = _seed_route(session, "BLR", "HYD")  # short-ish route, in basket
    _add_quote(session, cheap_route, 4000)

    pricey_route = _seed_route(session, "DEL", "SXR")  # short route, higher relative fare
    _add_quote(session, pricey_route, 9000)

    result = basket_affordability(session)
    assert len(result["routes"]) == 2
    assert result["cheapest_per_km_route"] is not None
    assert result["most_expensive_per_km_route"] is not None
    assert result["cost_per_km_gap_pct"] is not None
    assert result["cost_per_km_gap_pct"] >= 0
    # sorted descending by cost_per_km
    assert result["routes"][0]["cost_per_km"] >= result["routes"][-1]["cost_per_km"]


def test_basket_affordability_reports_the_real_wage_reference(session):
    result = basket_affordability(session)
    ref = result["wage_reference"]
    assert ref["casual_labour_daily_wage_male_inr"] == 455.0
    assert ref["casual_labour_daily_wage_female_inr"] == 315.0
    assert ref["report_label"] == "PLFS Annual Report 2025"
    assert ref["source_url"].startswith("https://www.mospi.gov.in/")
