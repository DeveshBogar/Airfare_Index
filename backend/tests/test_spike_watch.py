from __future__ import annotations

import datetime as dt

from app.config import TRAVEL_SPIKE_WINDOWS, spike_window_for_date
from app.db.models import Carrier, FareQuote, Route
from app.index.spike_watch import (
    basket_spike_watch,
    festival_route_prices,
    route_spike_signal,
    windows_in_scraping_horizon,
)


def test_spike_window_for_date_matches_known_diwali_2026_window():
    window = spike_window_for_date(dt.date(2026, 11, 8))
    assert window is not None
    assert window.key == "diwali_2026"


def test_spike_window_for_date_returns_none_outside_any_window():
    assert spike_window_for_date(dt.date(2026, 9, 9)) is None


def test_spike_window_for_date_resolves_overlaps_to_the_most_recently_begun_window():
    # Diwali (4-15 Nov) and Chhath (11-22 Nov) deliberately overlap; once
    # Chhath has begun it's the more specific signal for that date.
    assert spike_window_for_date(dt.date(2026, 11, 8)).key == "diwali_2026"  # Diwali only, Chhath not yet open
    assert spike_window_for_date(dt.date(2026, 11, 12)).key == "chhath_puja_2026"  # both open - Chhath began later
    # Chhath (11-22 Nov) and winter wedding season (20 Nov - 15 Feb) also overlap
    assert spike_window_for_date(dt.date(2026, 11, 21)).key == "winter_wedding_season_2026_27"
    # Christmas/New Year (20 Dec - 3 Jan) sits entirely inside wedding season
    assert spike_window_for_date(dt.date(2026, 12, 26)).key == "christmas_new_year_2026_27"


def test_spike_window_for_date_matches_every_window_at_its_own_start_date():
    # a window queried at its own start must always resolve to itself,
    # even where it overlaps a window that began earlier
    for window in TRAVEL_SPIKE_WINDOWS:
        assert spike_window_for_date(window.start).key == window.key


def test_windows_in_scraping_horizon_excludes_far_future_windows():
    as_of = dt.date(2026, 9, 9)
    horizon_end = as_of + dt.timedelta(days=45)  # matches max(AP_WINDOWS)
    in_horizon = windows_in_scraping_horizon(as_of, horizon_end)
    keys = {w.key for w in in_horizon}
    assert "durga_puja_dussehra_2026" in keys
    assert "diwali_2026" not in keys  # starts 4 Nov, past the 45-day horizon from 9 Sep


def _seed_route(session, origin="DEL", destination="PAT"):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    return route


def _add_quote(session, route, travel_date, total_fare):
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=30,
            search_date=dt.datetime.combine(dt.date(2026, 9, 9), dt.time.min),
            travel_date=dt.datetime.combine(travel_date, dt.time.min),
            fare_class="economy",
            base_fare=None,
            taxes_fees=None,
            total_fare=total_fare,
            is_outlier=False,
            sold_out=False,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_route_spike_signal_none_without_baseline_or_spike_data(session):
    route = _seed_route(session)
    _add_quote(session, route, dt.date(2026, 9, 20), 6000)  # not in any spike window
    _add_quote(session, route, dt.date(2026, 9, 21), 6100)
    assert route_spike_signal(session, route.id) is None  # no spike-window fares yet


def test_route_spike_signal_computes_real_premium(session):
    route = _seed_route(session)
    # baseline: two non-spike travel dates
    _add_quote(session, route, dt.date(2026, 9, 20), 6000)
    _add_quote(session, route, dt.date(2026, 9, 21), 6200)
    # spike: two travel dates inside the Durga Puja/Dussehra window (10-24 Oct 2026)
    _add_quote(session, route, dt.date(2026, 10, 18), 9000)
    _add_quote(session, route, dt.date(2026, 10, 19), 9400)

    signals = route_spike_signal(session, route.id)
    assert signals is not None
    assert len(signals) == 1
    signal = signals[0]
    assert signal["window_key"] == "durga_puja_dussehra_2026"
    assert signal["baseline_mean_fare"] == 6100
    assert signal["spike_mean_fare"] == 9200
    assert signal["pct_change"] > 40  # ~50.8% real premium in this fixture


def test_route_spike_signal_reports_honestly_when_no_premium(session):
    route = _seed_route(session)
    _add_quote(session, route, dt.date(2026, 9, 20), 9000)
    _add_quote(session, route, dt.date(2026, 9, 21), 9200)
    _add_quote(session, route, dt.date(2026, 10, 18), 8000)  # cheaper, not pricier
    _add_quote(session, route, dt.date(2026, 10, 19), 8200)

    signals = route_spike_signal(session, route.id)
    assert signals is not None
    assert signals[0]["pct_change"] < 0  # honestly negative, not clamped to "spike"


def test_basket_spike_watch_lists_full_calendar_regardless_of_data(session):
    result = basket_spike_watch(session, as_of=dt.date(2026, 9, 9), horizon_end=dt.date(2026, 10, 24))
    assert len(result["calendar"]) == len(TRAVEL_SPIKE_WINDOWS)
    durga = next(w for w in result["calendar"] if w["key"] == "durga_puja_dussehra_2026")
    assert durga["in_scraping_horizon"] is True
    diwali = next(w for w in result["calendar"] if w["key"] == "diwali_2026")
    assert diwali["in_scraping_horizon"] is False
    assert result["route_signals"] == []  # no fare data seeded in this test's session


def test_festival_route_prices_returns_none_for_unknown_window(session):
    assert festival_route_prices(session, "not_a_real_window") is None


def test_festival_route_prices_uses_real_data_inside_the_window(session):
    route = _seed_route(session, "DEL", "PAT")  # a real ROUTE_BASKET pair
    # Durga Puja & Dussehra 2026 window is 10-24 Oct
    _add_quote(session, route, dt.date(2026, 10, 15), 7000)
    _add_quote(session, route, dt.date(2026, 10, 18), 7400)

    result = festival_route_prices(session, "durga_puja_dussehra_2026", today=dt.date(2026, 9, 9))
    assert result is not None
    assert result["window_name"] == "Durga Puja & Dussehra"
    row = next(r for r in result["routes"] if r["route"] == "DEL-PAT")
    assert row["is_estimated"] is False
    assert row["price"] == 7000  # the cheapest real fare found, not the mean of the two
    assert row["sample_size"] == 2


def test_festival_route_prices_estimates_when_nothing_real_falls_in_window(session):
    route = _seed_route(session, "DEL", "PAT")
    # real data exists for this route, but not on any date inside the window
    _add_quote(session, route, dt.date(2026, 9, 20), 6500)
    _add_quote(session, route, dt.date(2026, 9, 21), 6700)

    result = festival_route_prices(session, "durga_puja_dussehra_2026", today=dt.date(2026, 9, 9))
    row = next(r for r in result["routes"] if r["route"] == "DEL-PAT")
    assert row["is_estimated"] is True
    assert row["sample_size"] == 0
    assert row["confidence"] is not None
    assert row["basis"] is not None


def test_festival_route_prices_computes_real_pct_change_when_both_sides_are_real(session):
    route = _seed_route(session, "DEL", "PAT")
    _add_quote(session, route, dt.date(2026, 10, 15), 9000)  # inside Durga Puja window
    _add_quote(session, route, dt.date(2026, 9, 20), 6000)  # ordinary day, no spike window
    _add_quote(session, route, dt.date(2026, 9, 21), 6000)

    result = festival_route_prices(session, "durga_puja_dussehra_2026", today=dt.date(2026, 9, 9))
    row = next(r for r in result["routes"] if r["route"] == "DEL-PAT")
    assert row["is_estimated"] is False
    assert row["baseline_is_estimated"] is False
    assert row["baseline_price"] == 6000
    assert row["baseline_sample_size"] == 2
    assert row["pct_change"] == 50.0  # 9000 vs 6000 = +50%


def test_festival_route_prices_estimates_baseline_when_only_festival_dates_are_real(session):
    # every real fare for this route falls INSIDE the window - there is no
    # real "ordinary day" price to compare against, so the baseline must
    # fall back to a (clearly flagged) non-spike-adjusted estimate
    route = _seed_route(session, "DEL", "PAT")
    _add_quote(session, route, dt.date(2026, 10, 15), 9000)
    _add_quote(session, route, dt.date(2026, 10, 18), 9400)

    result = festival_route_prices(session, "durga_puja_dussehra_2026", today=dt.date(2026, 9, 9))
    row = next(r for r in result["routes"] if r["route"] == "DEL-PAT")
    assert row["is_estimated"] is False  # the festival price itself is real
    assert row["baseline_is_estimated"] is True  # but the baseline had to be estimated
    assert row["baseline_sample_size"] == 0
    assert row["baseline_price"] is not None
    assert row["pct_change"] is not None


def test_festival_route_prices_pct_change_present_when_fully_estimated(session):
    # a route with zero real data of its own at all - both price and
    # baseline fall back to estimates, but a pct_change is still returned
    donor = _seed_route(session, "DEL", "BOM")
    for d, fare in ((dt.date(2026, 9, 20), 7800), (dt.date(2026, 9, 21), 8000), (dt.date(2026, 9, 22), 8200)):
        _add_quote(session, donor, d, fare)
    session.add(Route(origin="BLR", destination="HYD", display_name="BLR-HYD"))
    session.commit()

    result = festival_route_prices(session, "durga_puja_dussehra_2026", today=dt.date(2026, 9, 9))
    row = next(r for r in result["routes"] if r["route"] == "BLR-HYD")
    assert row["is_estimated"] is True
    assert row["baseline_is_estimated"] is True
    assert row["pct_change"] is not None
    assert row["range_low"] < row["price"] < row["range_high"]


def test_festival_route_prices_uses_its_own_researched_surge_not_an_overlapping_neighbour(session):
    # Chhath Puja (11-22 Nov) starts inside Diwali's window (4-15 Nov), and
    # winter wedding season (20 Nov - 15 Feb) starts inside Chhath's window
    # - each must still price off its OWN researched surge, not whichever
    # window happens to be listed earlier and also covers that start date.
    route = _seed_route(session, "DEL", "PAT")
    _add_quote(session, route, dt.date(2026, 9, 20), 6500)  # real data, but outside every spike window
    _add_quote(session, route, dt.date(2026, 9, 21), 6700)

    chhath = festival_route_prices(session, "chhath_puja_2026", today=dt.date(2026, 9, 9))
    row = next(r for r in chhath["routes"] if r["route"] == "DEL-PAT")
    assert "researched Chhath Puja surge" in row["basis"]
    assert "researched Diwali surge" not in row["basis"]

    wedding = festival_route_prices(session, "winter_wedding_season_2026_27", today=dt.date(2026, 9, 9))
    row = next(r for r in wedding["routes"] if r["route"] == "DEL-PAT")
    assert "researched Winter wedding season surge" in row["basis"]
    assert "researched Chhath Puja surge" not in row["basis"]


def test_festival_route_prices_sorts_routes_by_price(session):
    cheap = _seed_route(session, "DEL", "PAT")
    _add_quote(session, cheap, dt.date(2026, 10, 15), 5000)

    session.add(Carrier(code="QP", name="Akasa Air")) if session.get(Carrier, "QP") is None else None
    pricey = Route(origin="BLR", destination="HYD", display_name="Bengaluru-Hyderabad")
    session.add(pricey)
    session.commit()
    session.add(
        FareQuote(
            route_id=pricey.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=30,
            search_date=dt.datetime(2026, 9, 9),
            travel_date=dt.datetime(2026, 10, 15),
            fare_class="economy",
            total_fare=15000,
            is_outlier=False,
            sold_out=False,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()

    result = festival_route_prices(session, "durga_puja_dussehra_2026", today=dt.date(2026, 9, 9))
    prices = [r["price"] for r in result["routes"]]
    assert prices == sorted(prices)
