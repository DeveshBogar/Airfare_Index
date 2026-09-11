from __future__ import annotations

import datetime as dt

from app.config import AP_WINDOWS, ROUTE_BASKET
from app.db.models import Carrier, FareQuote, Route
from app.index.estimation import basket_price_grid, estimate_route_window, window_multipliers


def _seed_route(session, origin, destination):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    if session.get(Carrier, "SG") is None:
        session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    return route


def _add_quote(session, route, total_fare, ap_days, travel_date=None):
    search_date = dt.date(2026, 9, 4)
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=ap_days,
            search_date=dt.datetime.combine(search_date, dt.time.min),
            travel_date=dt.datetime.combine(travel_date or (search_date + dt.timedelta(days=ap_days)), dt.time.min),
            fare_class="economy",
            total_fare=total_fare,
            is_outlier=False,
            sold_out=False,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_window_multipliers_empty_db(session):
    result = window_multipliers(session)
    assert result["reference_window"] is None
    assert result["multipliers"] == {}


def test_window_multipliers_uses_most_sampled_window_as_reference(session):
    route = _seed_route(session, "DEL", "BOM")
    for _ in range(5):
        _add_quote(session, route, 7000, ap_days=7)
    _add_quote(session, route, 10000, ap_days=1)

    result = window_multipliers(session)
    assert result["reference_window"] == 7  # most samples
    assert result["multipliers"][7] == 1.0
    assert result["multipliers"][1] > 1.0  # T+1 is pricier than T+7 in this fixture


def test_window_multipliers_interpolates_a_totally_missing_window(session):
    route = _seed_route(session, "DEL", "BOM")
    for _ in range(3):
        _add_quote(session, route, 10000, ap_days=1)
    for _ in range(3):
        _add_quote(session, route, 6000, ap_days=15)
    # ap=7 has zero real quotes anywhere in this fixture, on either side of
    # the (1, 15) gap - it should be interpolated, not left undefined
    real_windows = {q.ap_window_days for q in session.query(FareQuote).all()}
    assert 7 not in real_windows

    result = window_multipliers(session)
    m = result["multipliers"]
    assert 7 in m
    assert m[1] > m[7] > m[15]


def test_estimate_uses_own_route_data_when_available(session):
    route = _seed_route(session, "DEL", "BOM")
    _add_quote(session, route, 8000, ap_days=7)
    _add_quote(session, route, 8200, ap_days=7)
    _add_quote(session, route, 9000, ap_days=1)

    mult_info = window_multipliers(session)
    # estimate a window this route has no data for (15), using its own T+1/T+7 data
    est = estimate_route_window(
        session, route, 15, mult_info, fallback_cost_per_km=None, travel_date=dt.date(2026, 9, 19)
    )
    assert est is not None
    assert est["confidence"] in ("high", "medium")
    assert "this route's own" in est["basis"]
    assert est["mean_fare"] > 0
    assert est["range_low"] < est["mean_fare"] < est["range_high"]


def test_estimate_falls_back_to_distance_when_route_has_no_data(session):
    # a route with real data (to build multipliers/fallback from)...
    donor = _seed_route(session, "DEL", "BOM")
    for _ in range(4):
        _add_quote(session, donor, 8000, ap_days=7)

    # ...and a route with ZERO real data, but real, known coordinates
    empty_route = _seed_route(session, "BLR", "HYD")

    mult_info = window_multipliers(session)
    from app.index.estimation import _basket_avg_normalized_cost_per_km

    fallback = _basket_avg_normalized_cost_per_km(session, mult_info["multipliers"])
    assert fallback is not None

    est = estimate_route_window(
        session, empty_route, 7, mult_info, fallback_cost_per_km=fallback, travel_date=dt.date(2026, 9, 11)
    )
    assert est is not None
    assert est["confidence"] == "low"
    assert "basket's average real cost per km" in est["basis"]


def test_basket_price_grid_flags_real_vs_estimated(session):
    route = _seed_route(session, "DEL", "BOM")  # a real basket pair
    _add_quote(session, route, 8000, ap_days=7)
    _add_quote(session, route, 8200, ap_days=7)
    _add_quote(session, route, 8100, ap_days=1)
    _add_quote(session, route, 8300, ap_days=1)

    result = basket_price_grid(session)
    assert result["total_cells"] == len(ROUTE_BASKET) * len(AP_WINDOWS)

    del_bom_cells = {c["ap_window_days"]: c for c in result["cells"] if c["route"] == "DEL-BOM"}
    assert del_bom_cells[7]["is_estimated"] is False
    assert del_bom_cells[7]["sample_size"] == 2
    assert del_bom_cells[15]["is_estimated"] is True
    assert del_bom_cells[15]["confidence"] is not None
    assert del_bom_cells[15]["range_low"] < del_bom_cells[15]["mean_fare"] < del_bom_cells[15]["range_high"]

    assert result["real_cells"] >= 2
    assert result["estimated_cells"] > 0
    assert result["real_cells"] + result["estimated_cells"] == len(result["cells"])


def test_basket_price_grid_real_cell_reports_the_cheapest_fare_not_the_mean(session):
    # a route's real quotes at one AP window mix a cheap fare class with
    # much pricier ones (mirrors SpiceJet's Saver/Flex/Max spread) - the
    # displayed number must be the real cheapest found, matching what an
    # actual booking search would show, not an average pulled up by the
    # premium classes.
    route = _seed_route(session, "DEL", "BOM")
    _add_quote(session, route, 7000, ap_days=7)  # cheapest
    _add_quote(session, route, 9000, ap_days=7)
    _add_quote(session, route, 11000, ap_days=7)

    result = basket_price_grid(session)
    cell = next(c for c in result["cells"] if c["route"] == "DEL-BOM" and c["ap_window_days"] == 7)
    assert cell["is_estimated"] is False
    assert cell["mean_fare"] == 7000  # not 9000, the mean of the three
    assert cell["sample_size"] == 3


def test_estimation_module_has_no_coupling_to_index_construction():
    # documentation-as-test: estimates must never be able to leak into the
    # real index by accident of a shared import or a copy-pasted call
    import inspect

    import app.index.estimation as mod

    src = inspect.getsource(mod)
    assert "IndexValue" not in src
    assert "compute_index_series" not in src
    assert "run_index_construction" not in src
