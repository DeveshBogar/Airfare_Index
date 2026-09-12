from __future__ import annotations

import datetime as dt

from app.db.models import Carrier, FareQuote, Route
from app.index.carrier_index import (
    active_carriers,
    compute_all_carrier_index_series,
    compute_carrier_weights,
)
from app.index.construct import compute_index_series


def _route(session, origin, destination):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    session.commit()
    return route


def _carrier(session, code, name):
    existing = session.get(Carrier, code)
    if existing:
        return existing
    c = Carrier(code=code, name=name)
    session.add(c)
    session.commit()
    return c


def _quote(session, route, carrier_code, source_id, search_date, total_fare, ap_days=7):
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code=carrier_code,
            source_id=source_id,
            ap_window_days=ap_days,
            search_date=dt.datetime.combine(search_date, dt.time.min),
            travel_date=dt.datetime.combine(search_date + dt.timedelta(days=ap_days), dt.time.min),
            fare_class="economy",
            total_fare=total_fare,
            is_outlier=False,
            sold_out=False,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_active_carriers_lists_only_carriers_with_real_priced_quotes(session):
    route = _route(session, "DEL", "BOM")
    _carrier(session, "SG", "SpiceJet")
    _carrier(session, "QP", "Akasa Air")
    d = dt.date(2026, 9, 4)
    _quote(session, route, "SG", "spicejet", d, 7000)
    # QP has only a sold-out row -> not "active" (no real price observed)
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code="QP",
            source_id="akasa",
            ap_window_days=7,
            search_date=dt.datetime.combine(d, dt.time.min),
            travel_date=dt.datetime.combine(d + dt.timedelta(days=7), dt.time.min),
            fare_class="economy",
            total_fare=None,
            is_outlier=False,
            sold_out=True,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()

    assert active_carriers(session) == ["SG"]


def test_carrier_index_series_scopes_to_that_carriers_own_fares(session):
    # Two carriers on one route: SG's fares double, QP's fares stay flat.
    # The per-carrier series must each reflect only their own movement -
    # not the whole-market cheapest-of-either-carrier figure.
    route = _route(session, "DEL", "BOM")
    _carrier(session, "SG", "SpiceJet")
    _carrier(session, "QP", "Akasa Air")
    d0, d1 = dt.date(2026, 9, 4), dt.date(2026, 9, 5)

    _quote(session, route, "SG", "spicejet", d0, 5000)
    _quote(session, route, "SG", "spicejet", d1, 10000)  # SG: +100%
    _quote(session, route, "QP", "akasa", d0, 6000)
    _quote(session, route, "QP", "akasa", d1, 6000)  # QP: flat

    sg_series = compute_index_series(session, carrier_code="SG")
    qp_series = compute_index_series(session, carrier_code="QP")

    assert abs(sg_series[-1]["fisher"] - 200.0) < 1e-6
    assert abs(qp_series[-1]["fisher"] - 100.0) < 1e-6


def test_carrier_weights_split_by_real_dgca_route_weight_and_observed_quote_share(session):
    # Single-route basket -> that route's DGCA weight is 1.0 by
    # construction (compute_route_weights normalizes over whatever basket
    # it's given), so the carrier split on this route IS the whole
    # weight split: 2 SG quotes vs 1 QP quote -> SG=2/3, QP=1/3.
    route = _route(session, "DEL", "BOM")
    _carrier(session, "SG", "SpiceJet")
    _carrier(session, "QP", "Akasa Air")
    d = dt.date(2026, 9, 4)
    _quote(session, route, "SG", "spicejet", d, 7000, ap_days=1)
    _quote(session, route, "SG", "spicejet", d, 7200, ap_days=7)
    _quote(session, route, "QP", "akasa", d, 6800, ap_days=1)

    weights = compute_carrier_weights(session)
    assert abs(weights["SG"] - 2 / 3) < 1e-6
    assert abs(weights["QP"] - 1 / 3) < 1e-6
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_carrier_weights_partition_across_two_routes_with_different_dgca_weight(session):
    # BOM-DEL carries far more real DGCA traffic than DEL-PAT, so a
    # carrier that only appears on the low-traffic route should end up
    # with a small overall weight even with equal quote counts per route.
    bom_del = _route(session, "BOM", "DEL")
    del_pat = _route(session, "DEL", "PAT")
    _carrier(session, "SG", "SpiceJet")
    _carrier(session, "QP", "Akasa Air")
    d = dt.date(2026, 9, 4)
    _quote(session, bom_del, "SG", "spicejet", d, 7000)
    _quote(session, del_pat, "QP", "akasa", d, 6800)

    weights = compute_carrier_weights(session)
    # SG (BOM-DEL, the bigger real route) must outweigh QP (DEL-PAT)
    assert weights["SG"] > weights["QP"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_compute_all_carrier_index_series_attaches_a_constant_weight_per_carrier(session):
    route = _route(session, "DEL", "BOM")
    _carrier(session, "SG", "SpiceJet")
    d0, d1 = dt.date(2026, 9, 4), dt.date(2026, 9, 5)
    _quote(session, route, "SG", "spicejet", d0, 7000)
    _quote(session, route, "SG", "spicejet", d1, 7500)

    by_carrier = compute_all_carrier_index_series(session)
    assert set(by_carrier.keys()) == {"SG"}
    points = by_carrier["SG"]
    assert len(points) == 2
    assert all(p["carrier_weight"] == points[0]["carrier_weight"] for p in points)
    assert abs(points[0]["carrier_weight"] - 1.0) < 1e-9  # sole carrier -> full weight


def test_compute_all_carrier_index_series_empty_when_no_data(session):
    assert compute_all_carrier_index_series(session) == {}
