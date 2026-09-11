from __future__ import annotations

import datetime as dt

from app.db.models import Carrier, FareQuote, Route
from app.index.price_history import route_price_history


def _seed_route(session, origin="DEL", destination="BOM"):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    return route


def _add_quote(session, route, search_date, total_fare, ap_days=7, sold_out=False, is_outlier=False):
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=ap_days,
            search_date=dt.datetime.combine(search_date, dt.time.min),
            travel_date=dt.datetime.combine(search_date + dt.timedelta(days=ap_days), dt.time.min),
            fare_class="economy",
            total_fare=total_fare,
            is_outlier=is_outlier,
            sold_out=sold_out,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_route_price_history_returns_none_for_unknown_route(session):
    assert route_price_history(session, route_id=99999) is None


def test_route_price_history_reports_zero_days_with_no_real_data(session):
    route = _seed_route(session)
    result = route_price_history(session, route_id=route.id)
    assert result is not None
    assert result["days_of_history"] == 0
    assert result["points"] == []
    assert result["typical_low"] is None
    assert result["typical_high"] is None
    assert result["latest_cheapest_fare"] is None


def test_route_price_history_groups_by_calendar_day(session):
    route = _seed_route(session)
    _add_quote(session, route, dt.date(2026, 9, 4), 8000)
    _add_quote(session, route, dt.date(2026, 9, 4), 8500)  # same day, different fare
    _add_quote(session, route, dt.date(2026, 9, 7), 7000)

    result = route_price_history(session, route_id=route.id)
    assert result["days_of_history"] == 2
    day1, day2 = result["points"]
    assert day1["search_date"] == dt.date(2026, 9, 4)
    assert day1["cheapest_fare"] == 8000
    assert day1["mean_fare"] == 8250
    assert day1["sample_size"] == 2
    assert day2["search_date"] == dt.date(2026, 9, 7)
    assert day2["cheapest_fare"] == 7000
    assert day2["sample_size"] == 1


def test_route_price_history_points_are_sorted_ascending_by_date(session):
    route = _seed_route(session)
    _add_quote(session, route, dt.date(2026, 9, 10), 6000)
    _add_quote(session, route, dt.date(2026, 9, 4), 8000)
    _add_quote(session, route, dt.date(2026, 9, 7), 7000)

    result = route_price_history(session, route_id=route.id)
    dates = [p["search_date"] for p in result["points"]]
    assert dates == sorted(dates)


def test_route_price_history_latest_reflects_most_recent_day(session):
    route = _seed_route(session)
    _add_quote(session, route, dt.date(2026, 9, 4), 8000)
    _add_quote(session, route, dt.date(2026, 9, 10), 6500)

    result = route_price_history(session, route_id=route.id)
    assert result["latest_search_date"] == dt.date(2026, 9, 10)
    assert result["latest_cheapest_fare"] == 6500


def test_route_price_history_excludes_sold_out_and_outlier_rows(session):
    route = _seed_route(session)
    _add_quote(session, route, dt.date(2026, 9, 4), 8000)
    _add_quote(session, route, dt.date(2026, 9, 4), 500, sold_out=True)
    _add_quote(session, route, dt.date(2026, 9, 4), 99999, is_outlier=True)

    result = route_price_history(session, route_id=route.id)
    assert result["points"][0]["sample_size"] == 1
    assert result["points"][0]["cheapest_fare"] == 8000


def test_route_price_history_typical_range_brackets_a_single_real_day(session):
    # a single real day is the honest degenerate case: the "typical range"
    # collapses to that one observed value rather than fabricating a band
    route = _seed_route(session)
    _add_quote(session, route, dt.date(2026, 9, 4), 8000)

    result = route_price_history(session, route_id=route.id)
    assert result["typical_low"] == result["typical_high"] == 8000
    assert result["lowest_seen"] == result["highest_seen"] == 8000


def test_route_price_history_typical_range_reflects_real_spread(session):
    route = _seed_route(session)
    for day, fare in [
        (dt.date(2026, 9, 1), 5000),
        (dt.date(2026, 9, 2), 6000),
        (dt.date(2026, 9, 3), 7000),
        (dt.date(2026, 9, 4), 8000),
        (dt.date(2026, 9, 5), 9000),
    ]:
        _add_quote(session, route, day, fare)

    result = route_price_history(session, route_id=route.id)
    assert result["lowest_seen"] == 5000
    assert result["highest_seen"] == 9000
    # typical band sits strictly inside the full observed range, not
    # collapsed to the extremes
    assert result["lowest_seen"] < result["typical_low"] <= result["typical_high"] < result["highest_seen"]
