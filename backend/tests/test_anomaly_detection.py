from __future__ import annotations

import datetime as dt

from app.db.models import Carrier, FareQuote, RegulatorFareFlag, Route
from app.index.anomaly_detection import (
    MIN_HISTORY_DAYS_FOR_ANOMALY_CHECK,
    MIN_PCT_ABOVE_BASELINE_FOR_FLAG,
    NEWS_LOOKBACK_DAYS,
    detect_all_anomalies,
    detect_anomaly_for_group,
    persist_anomaly_flags,
    why_context_for_flag,
)

NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"


def _route(session, origin="DEL", destination="BOM"):
    route = Route(origin=origin, destination=destination, display_name=f"{origin}-{destination}")
    session.add(route)
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    return route


def _quote(session, route, search_date, total_fare, ap_days=7, carrier="SG"):
    session.add(
        FareQuote(
            route_id=route.id,
            carrier_code=carrier,
            source_id="spicejet",
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


def _seed_history(session, route, fares, start=dt.date(2026, 9, 1), ap_days=7):
    for i, fare in enumerate(fares):
        _quote(session, route, start + dt.timedelta(days=i), fare, ap_days=ap_days)


def _offline_gate(monkeypatch):
    """Keeps why_context_for_flag's live news/compliance lookups off the
    network in tests."""
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )
    monkeypatch.setattr("app.news.fetch_news._cache", {})
    monkeypatch.setattr(
        "app.news.fetch_news._fetch_all",
        lambda gate: type(
            "R",
            (),
            {"items": [], "as_of": dt.datetime.now(dt.timezone.utc), "sources_checked": []},
        )(),
    )


def test_no_flag_below_minimum_history(session):
    route = _seed_route = _route(session)
    # Exactly MIN_HISTORY_DAYS_FOR_ANOMALY_CHECK days total means only
    # MIN-1 baseline days once the tested day is set aside — not enough.
    fares = [7000.0] * (MIN_HISTORY_DAYS_FOR_ANOMALY_CHECK - 1) + [99000.0]
    _seed_history(session, route, fares)
    assert detect_anomaly_for_group(session, route.id, "SG", 7) is None


def test_no_flag_when_baseline_has_no_spread(session):
    route = _route(session)
    # A perfectly flat baseline has MAD == 0 — no scale to judge against.
    _seed_history(session, route, [7000.0, 7000.0, 7000.0, 7000.0, 9000.0])
    assert detect_anomaly_for_group(session, route.id, "SG", 7) is None


def test_no_flag_when_fare_is_cheaper_than_history(session):
    route = _route(session)
    # The directional guard: a bargain is not a regulatory concern, even
    # though it is just as far from the baseline in absolute terms.
    _seed_history(session, route, [7000.0, 7100.0, 6900.0, 7050.0, 1000.0])
    assert detect_anomaly_for_group(session, route.id, "SG", 7) is None


def test_no_flag_when_statistically_unusual_but_not_materially_elevated(session):
    # The real case this guard exists for: a route whose fares barely move
    # has a tiny MAD, so a small increase scores a huge z-score. Here the
    # baseline is 7000 +/- 5 and the tested day is 7350 (+5%) — z is far
    # past the cutoff, but 5% is not something worth a regulator's time.
    route = _route(session)
    _seed_history(session, route, [7000.0, 7005.0, 6995.0, 7000.0, 7350.0])

    candidate = detect_anomaly_for_group(session, route.id, "SG", 7)
    assert candidate is None


def test_materiality_floor_still_lets_a_serious_spike_through(session):
    route = _route(session)
    # Same ultra-stable baseline, but a genuinely large jump (+50%).
    _seed_history(session, route, [7000.0, 7005.0, 6995.0, 7000.0, 10500.0])

    candidate = detect_anomaly_for_group(session, route.id, "SG", 7)
    assert candidate is not None
    assert candidate.pct_above_baseline_median >= MIN_PCT_ABOVE_BASELINE_FOR_FLAG


def test_flags_a_clearly_elevated_fare_with_real_numbers(session):
    route = _route(session)
    _seed_history(session, route, [7000.0, 7100.0, 6900.0, 7050.0, 21000.0])

    found = detect_anomaly_for_group(session, route.id, "SG", 7)
    assert found is not None
    assert found.observed_fare == 21000.0
    assert found.baseline_sample_size == 4
    assert found.robust_z_score > 3.5
    assert found.baseline_median_fare == 7025.0  # median of the 4 prior days
    assert found.pct_above_baseline_median > 100
    # travel date is derived deterministically from the AP window
    assert found.flagged_travel_date == found.flagged_search_date + dt.timedelta(days=7)


def test_detect_all_anomalies_scopes_per_carrier(session):
    route = _route(session)
    session.add(Carrier(code="QP", name="Akasa Air"))
    session.commit()
    # SG spikes; QP stays flat on the same route and window.
    _seed_history(session, route, [7000.0, 7100.0, 6900.0, 7050.0, 21000.0])
    for i, fare in enumerate([5000.0, 5100.0, 4900.0, 5050.0, 5000.0]):
        _quote(session, route, dt.date(2026, 9, 1) + dt.timedelta(days=i), fare, carrier="QP")

    found = detect_all_anomalies(session)
    assert [c.carrier_code for c in found] == ["SG"]


def test_persist_anomaly_flags_is_idempotent(session):
    route = _route(session)
    _seed_history(session, route, [7000.0, 7100.0, 6900.0, 7050.0, 21000.0])

    candidates = detect_all_anomalies(session)
    assert persist_anomaly_flags(session, candidates) == 1
    session.commit()
    # Re-running the same detection must not duplicate the group-day.
    assert persist_anomaly_flags(session, candidates) == 0
    assert session.query(RegulatorFareFlag).count() == 1


def test_persist_does_not_overwrite_an_existing_review(session):
    route = _route(session)
    _seed_history(session, route, [7000.0, 7100.0, 6900.0, 7050.0, 21000.0])
    candidates = detect_all_anomalies(session)
    persist_anomaly_flags(session, candidates)
    session.commit()

    flag = session.query(RegulatorFareFlag).one()
    flag.status = "dismissed"
    flag.review_note = "festival week, expected"
    session.commit()

    persist_anomaly_flags(session, candidates)
    session.commit()
    refreshed = session.query(RegulatorFareFlag).one()
    assert refreshed.status == "dismissed"
    assert refreshed.review_note == "festival week, expected"


def test_why_context_includes_festival_window_only_when_the_date_falls_inside_one(session, monkeypatch):
    _offline_gate(monkeypatch)
    # Diwali 2026 window in app.config.TRAVEL_SPIKE_WINDOWS runs 4-15 Nov 2026.
    inside = why_context_for_flag(
        session, "SG", dt.date(2026, 11, 8), dt.date(2026, 11, 1)
    )
    outside = why_context_for_flag(
        session, "SG", dt.date(2026, 7, 8), dt.date(2026, 7, 1)
    )
    assert any(f["factor_type"] == "festival_demand_window" for f in inside)
    assert not any(f["factor_type"] == "festival_demand_window" for f in outside)


def test_why_context_always_reports_carrier_financial_availability(session, monkeypatch):
    _offline_gate(monkeypatch)
    listed = why_context_for_flag(session, "SG", dt.date(2026, 7, 8), dt.date(2026, 7, 1))
    unlisted = why_context_for_flag(session, "QP", dt.date(2026, 7, 8), dt.date(2026, 7, 1))

    sg = next(f for f in listed if f["factor_type"] == "carrier_financial_context")
    qp = next(f for f in unlisted if f["factor_type"] == "carrier_financial_context")
    assert sg["available"] is True and sg["latest_quarter"] is not None
    # Akasa is privately held — reported honestly as unavailable, not guessed.
    assert qp["available"] is False and qp["latest_quarter"] is None
    assert qp["reason"]


def test_why_context_respects_the_news_lookback_window(session, monkeypatch):
    _offline_gate(monkeypatch)
    flagged_day = dt.date(2026, 7, 10)

    class FakeItem:
        def __init__(self, day, title):
            self.title = title
            self.link = "https://example.com/x"
            self.source = "Test Source"
            self.published_at = dt.datetime.combine(day, dt.time(12, 0), tzinfo=dt.timezone.utc)
            self.categories = ["fuel"]
            self.summary = "s"

    in_window = FakeItem(flagged_day - dt.timedelta(days=NEWS_LOOKBACK_DAYS - 1), "recent")
    too_old = FakeItem(flagged_day - dt.timedelta(days=NEWS_LOOKBACK_DAYS + 5), "stale")
    monkeypatch.setattr(
        "app.news.fetch_news._fetch_all",
        lambda gate: type(
            "R",
            (),
            {
                "items": [in_window, too_old],
                "as_of": dt.datetime.now(dt.timezone.utc),
                "sources_checked": [],
            },
        )(),
    )

    factors = why_context_for_flag(session, "SG", flagged_day + dt.timedelta(days=7), flagged_day)
    titles = [f["title"] for f in factors if f["factor_type"] == "news_item"]
    assert "recent" in titles
    assert "stale" not in titles


def test_why_context_survives_an_unreachable_news_source(session, monkeypatch):
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )
    monkeypatch.setattr("app.news.fetch_news._cache", {})

    def boom(gate):
        raise RuntimeError("news source down")

    monkeypatch.setattr("app.news.fetch_news._fetch_all", boom)

    # News is context, not the finding — its failure must not lose the flag.
    factors = why_context_for_flag(session, "SG", dt.date(2026, 7, 8), dt.date(2026, 7, 1))
    assert any(f["factor_type"] == "carrier_financial_context" for f in factors)
