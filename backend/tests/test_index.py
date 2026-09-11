from __future__ import annotations

import datetime as dt

from app.db.models import Carrier, FareQuote, Route
from app.index.booking_advice import booking_advice
from app.index.construct import cheapest_by_route_day, compute_index_series
from app.index.elasticity import lead_time_curve
from app.index.weights import compute_route_weights, normalize_city, top_traffic_routes


def test_normalize_city_strips_whitespace_and_airport_suffix():
    assert normalize_city(" JAIPUR ") == "JAIPUR"
    assert normalize_city("DEOGHAR AIRPORT") == "DEOGHAR"
    assert normalize_city("KUSHINAGAR INTERNATIONAL AIRPORT") == "KUSHINAGAR"


def test_normalize_city_resolves_known_duplicate_labels():
    # this is the real bug found in the DGCA CSV: "MUMBAI (MUMBAI)" is the
    # same city as "MUMBAI" but was silently splitting Mumbai's traffic in
    # two before normalize_city existed
    assert normalize_city("MUMBAI (MUMBAI)") == "MUMBAI"
    assert normalize_city("mumbai (mumbai)") == "MUMBAI"
    assert normalize_city("COCHIN") == "KOCHI"


def test_top_traffic_routes_merges_duplicate_city_labels():
    # Delhi-Mumbai must outrank Bengaluru-Delhi once the "MUMBAI (MUMBAI)"
    # rows are correctly folded into "MUMBAI" — this was false before the
    # normalization fix (Bengaluru-Delhi looked bigger with Mumbai's
    # traffic artificially split across two labels)
    ranked = top_traffic_routes(n=5)
    top_pair, top_pax = ranked[0]
    assert set(top_pair) == {"BOM", "DEL"}
    # every route in the top 5 should have both ends resolvable to a name
    assert len(ranked) == 5
    assert all(pax > 0 for _, pax in ranked)


def test_compute_route_weights_uses_real_dgca_data_and_normalizes():
    weights = compute_route_weights([("DEL", "BOM"), ("DEL", "BLR")])
    assert set(weights.keys()) == {("DEL", "BOM"), ("DEL", "BLR")}
    assert all(w["passengers"] > 0 for w in weights.values())
    total = sum(w["weight"] for w in weights.values())
    assert abs(total - 1.0) < 1e-9


def _seed_route(session, origin="DEL", destination="BOM"):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    return route


def _add_quote(session, route, search_date, total_fare, ap_days=7, is_outlier=False, sold_out=False):
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=ap_days,
            search_date=dt.datetime.combine(search_date, dt.time.min),
            travel_date=dt.datetime.combine(search_date + dt.timedelta(days=ap_days), dt.time.min),
            fare_class="economy",
            base_fare=None,
            taxes_fees=None,
            total_fare=total_fare,
            is_outlier=is_outlier,
            sold_out=sold_out,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_cheapest_by_route_day_picks_the_minimum(session):
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 8000)
    _add_quote(session, route, d, 7000)
    _add_quote(session, route, d, 7500)
    cheapest = cheapest_by_route_day(session)
    assert cheapest[(route.id, d)] == 7000


def test_cheapest_by_route_day_excludes_outliers_and_sold_out(session):
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 7000)
    _add_quote(session, route, d, 500, is_outlier=True)  # would win on price but is flagged
    _add_quote(session, route, d, 100, sold_out=True)
    cheapest = cheapest_by_route_day(session)
    assert cheapest[(route.id, d)] == 7000


def test_index_series_base_day_equals_100(session):
    route = _seed_route(session)
    d0 = dt.date(2026, 9, 4)
    d1 = dt.date(2026, 9, 5)
    _add_quote(session, route, d0, 7000)
    _add_quote(session, route, d1, 8400)  # 20% up
    series = compute_index_series(session)
    assert len(series) == 2
    assert series[0]["date"] == d0
    for method in ("laspeyres", "paasche", "fisher"):
        assert abs(series[0][method] - 100.0) < 1e-6
    # single-route basket -> weight cancels out, relative price fully drives the index
    assert abs(series[1]["laspeyres"] - 120.0) < 1e-6


def test_index_series_empty_when_no_data(session):
    assert compute_index_series(session) == []


def test_lead_time_curve_reports_mean_and_elasticity_sign(session):
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 15000, ap_days=1)
    _add_quote(session, route, d, 14000, ap_days=1)
    _add_quote(session, route, d, 7000, ap_days=45)
    _add_quote(session, route, d, 7200, ap_days=45)
    curve = lead_time_curve(session, route_id=route.id)
    windows = {c["ap_window_days"]: c for c in curve}
    assert windows[1]["mean_fare"] == 14500
    assert windows[45]["mean_fare"] == 7100
    # fares should be cheaper the further out you book
    assert windows[45]["mean_fare"] < windows[1]["mean_fare"]


def test_booking_advice_reports_no_signal_with_one_window(session):
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 7000, ap_days=7)
    advice = booking_advice(session, route_id=route.id)
    assert advice["has_signal"] is False
    assert advice["windows_with_data"] == 1


def test_booking_advice_recommends_booking_early_when_lead_time_pays_off(session):
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 15000, ap_days=1)
    _add_quote(session, route, d, 7000, ap_days=45)
    advice = booking_advice(session, route_id=route.id)
    assert advice["has_signal"] is True
    assert advice["verdict"] == "book_early"
    assert advice["cheapest_window_days"] == 45
    assert advice["priciest_window_days"] == 1
    assert advice["gap_pct"] > 50


def test_booking_advice_recommends_waiting_when_last_minute_is_cheaper(session):
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 6000, ap_days=1)
    _add_quote(session, route, d, 12000, ap_days=45)
    advice = booking_advice(session, route_id=route.id)
    assert advice["verdict"] == "can_wait"
    assert advice["cheapest_window_days"] == 1


def test_booking_advice_reports_no_strong_pattern_for_a_small_gap(session):
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 7000, ap_days=1)
    _add_quote(session, route, d, 7100, ap_days=45)
    advice = booking_advice(session, route_id=route.id)
    assert advice["verdict"] == "no_strong_pattern"


def test_booking_advice_reports_the_real_minimum_fare_not_the_window_mean(session):
    # each window mixes several real quotes (different fare classes), so
    # a window's mean and minimum genuinely differ - the displayed
    # "cheapest so far" / "priciest so far" fare must be the real minimum
    # actually seen in that window, matching what a booking search would
    # show, not an average pulled up by pricier fare classes. Window
    # SELECTION (which is cheaper) legitimately stays mean-based - that's
    # a distinct, valid statistical question about the lead-time pattern.
    route = _seed_route(session)
    d = dt.date(2026, 9, 4)
    _add_quote(session, route, d, 7000, ap_days=45)
    _add_quote(session, route, d, 9000, ap_days=45)  # window 45: mean=8000, min=7000
    _add_quote(session, route, d, 14000, ap_days=1)
    _add_quote(session, route, d, 16000, ap_days=1)  # window 1: mean=15000, min=14000

    advice = booking_advice(session, route_id=route.id)
    assert advice["cheapest_window_days"] == 45
    assert advice["cheapest_mean_fare"] == 7000
    assert advice["priciest_window_days"] == 1
    assert advice["priciest_mean_fare"] == 14000
