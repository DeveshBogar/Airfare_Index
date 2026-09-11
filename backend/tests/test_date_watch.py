from __future__ import annotations

import datetime as dt

from app.db.models import Carrier, FareQuote, Route
from app.index.date_watch import date_watch


def _seed_route(session, origin="DEL", destination="BOM"):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    return route


def _add_quote(session, route, travel_date, ap_days, total_fare=None, sold_out=False, search_date=None):
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=ap_days,
            search_date=dt.datetime.combine(search_date or (travel_date - dt.timedelta(days=ap_days)), dt.time.min),
            travel_date=dt.datetime.combine(travel_date, dt.time.min),
            fare_class="economy",
            base_fare=None,
            taxes_fees=None,
            total_fare=total_fare,
            is_outlier=False,
            sold_out=sold_out,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_date_watch_with_no_data_reports_honestly(session):
    route = _seed_route(session)
    result = date_watch(session, route.id, dt.date(2026, 10, 19), today=dt.date(2026, 9, 9))
    assert result["has_signal"] is False
    assert "No real prices" in result["message"]
    assert len(result["checkpoints"]) == 5
    statuses = {c["ap_window_days"]: c["status"] for c in result["checkpoints"]}
    # the 45-day checkpoint (4 Sep) has already passed today (9 Sep) with no data collected
    assert statuses[45] == "missed"
    # the rest (19 Sep, 4 Oct, 12 Oct, 18 Oct) are still ahead of today
    assert statuses[30] == statuses[15] == statuses[7] == statuses[1] == "upcoming"


def test_date_watch_single_point_reports_but_no_verdict(session):
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    _add_quote(session, route, travel_date, ap_days=45, total_fare=8000)
    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 9, 9))
    assert result["has_signal"] is False
    assert result["cheapest_so_far"]["mean_fare"] == 8000
    checkpoint_45 = next(c for c in result["checkpoints"] if c["ap_window_days"] == 45)
    assert checkpoint_45["status"] == "collected"
    # the 30-day checkpoint (19 Sep) is still ahead of "today" (9 Sep)
    checkpoint_30 = next(c for c in result["checkpoints"] if c["ap_window_days"] == 30)
    assert checkpoint_30["status"] == "upcoming"
    assert checkpoint_30["checkpoint_date"] == dt.date(2026, 9, 19)


def test_date_watch_two_points_gives_a_real_verdict(session):
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    _add_quote(session, route, travel_date, ap_days=45, total_fare=8000)  # checkpoint 4 Sep
    _add_quote(session, route, travel_date, ap_days=30, total_fare=11000)  # checkpoint 19 Sep
    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 9, 25))
    assert result["has_signal"] is True
    assert result["cheapest_so_far"]["ap_window_days"] == 45
    assert result["priciest_so_far"]["ap_window_days"] == 30
    assert abs(result["gap_pct"] - 27.3) < 0.5


def test_date_watch_cheapest_so_far_uses_the_real_minimum_not_the_mean(session):
    # each checkpoint mixes multiple real quotes (different fare classes),
    # so a checkpoint's mean and minimum genuinely differ - cheapest_so_far
    # must select and report by the real minimum, matching what a booking
    # search would actually show, not an average pulled up by pricier
    # fare classes.
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    _add_quote(session, route, travel_date, ap_days=45, total_fare=7000)
    _add_quote(session, route, travel_date, ap_days=45, total_fare=9000)  # mean=8000, min=7000
    _add_quote(session, route, travel_date, ap_days=30, total_fare=11000)
    _add_quote(session, route, travel_date, ap_days=30, total_fare=13000)  # mean=12000, min=11000

    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 9, 25))
    assert result["cheapest_so_far"]["ap_window_days"] == 45
    assert result["cheapest_so_far"]["min_fare"] == 7000
    assert result["priciest_so_far"]["min_fare"] == 11000
    assert "7000" in result["message"]
    assert "8000" not in result["message"]


def test_date_watch_marks_a_past_checkpoint_with_no_data_as_missed(session):
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    # today is 6 Oct: the 45/30/15-day checkpoints (4 Sep, 19 Sep, 4 Oct) have all
    # already passed with nothing scraped for them
    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 10, 6))
    statuses = {c["ap_window_days"]: c["status"] for c in result["checkpoints"]}
    assert statuses[45] == "missed"
    assert statuses[30] == "missed"
    assert statuses[15] == "missed"
    assert statuses[7] == "upcoming"  # 12 Oct, still ahead
    assert statuses[1] == "upcoming"  # 18 Oct, still ahead


def test_date_watch_marks_todays_checkpoint_as_checking_today(session):
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 10, 12))  # 19 Oct - 7 = 12 Oct
    checkpoint_7 = next(c for c in result["checkpoints"] if c["ap_window_days"] == 7)
    assert checkpoint_7["status"] == "checking_today"


def test_date_watch_reports_sold_out_checkpoint(session):
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    _add_quote(session, route, travel_date, ap_days=45, total_fare=None, sold_out=True)
    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 9, 9))
    checkpoint_45 = next(c for c in result["checkpoints"] if c["ap_window_days"] == 45)
    assert checkpoint_45["status"] == "sold_out"


def test_date_watch_fills_missing_checkpoints_with_flagged_estimates(session):
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    # enough real data at two windows to build a route-specific base
    _add_quote(session, route, travel_date, ap_days=45, total_fare=8000)
    _add_quote(session, route, travel_date, ap_days=1, total_fare=10000)

    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 9, 9))
    checkpoint_15 = next(c for c in result["checkpoints"] if c["ap_window_days"] == 15)
    assert checkpoint_15["status"] == "upcoming"  # still honestly reports why there's no real data
    assert checkpoint_15["is_estimated"] is True
    assert checkpoint_15["mean_fare"] is not None
    assert checkpoint_15["confidence"] in ("high", "medium", "low")
    assert checkpoint_15["basis"] is not None
    assert checkpoint_15["range_low"] < checkpoint_15["mean_fare"] < checkpoint_15["range_high"]


def test_date_watch_never_estimates_a_sold_out_checkpoint(session):
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    _add_quote(session, route, travel_date, ap_days=45, total_fare=8000)
    _add_quote(session, route, travel_date, ap_days=1, total_fare=None, sold_out=True)

    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 9, 9))
    checkpoint_1 = next(c for c in result["checkpoints"] if c["ap_window_days"] == 1)
    assert checkpoint_1["status"] == "sold_out"
    assert checkpoint_1["is_estimated"] is False
    assert checkpoint_1["mean_fare"] is None  # never substitute a price for a known sold-out flight


def test_date_watch_verdict_still_ignores_estimated_checkpoints(session):
    # only one REAL checkpoint - estimates fill in the rest of the row for
    # display, but the verdict must stay based on real data only
    route = _seed_route(session)
    travel_date = dt.date(2026, 10, 19)
    _add_quote(session, route, travel_date, ap_days=45, total_fare=8000)

    result = date_watch(session, route.id, travel_date, today=dt.date(2026, 9, 9))
    estimated = [c for c in result["checkpoints"] if c["is_estimated"]]
    assert len(estimated) >= 1  # the fill-in did happen
    assert result["has_signal"] is False  # but a single real point still isn't a verdict
    assert result["cheapest_so_far"]["mean_fare"] == 8000
    assert result["cheapest_so_far"]["is_estimated"] is False
