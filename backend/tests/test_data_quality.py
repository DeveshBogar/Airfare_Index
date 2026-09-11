from __future__ import annotations

import datetime as dt

from app.data_quality import validate_data
from app.db.models import Carrier, FareQuote, Route, ScrapeRun


def _find(result, check_name):
    return next(c for c in result["checks"] if c["check"] == check_name)


def test_validate_data_all_ok_on_empty_db(session):
    result = validate_data(session)
    assert result["all_ok"] is True


def test_validate_data_flags_duplicate_routes(session):
    session.add(Route(origin="DEL", destination="BOM", display_name="Delhi-Mumbai"))
    session.add(Route(origin="BOM", destination="DEL", display_name="Mumbai-Delhi"))  # same pair, wrong direction
    session.commit()

    result = validate_data(session)
    check = _find(result, "duplicate_routes")
    assert check["ok"] is False
    assert result["all_ok"] is False


def test_validate_data_flags_orphaned_fare_quotes(session):
    # a FareQuote pointing at a route_id that doesn't exist — the
    # foreign_keys=ON pragma (app.db.session) prevents this on the real
    # app database, but the in-memory test engine doesn't enable it, which
    # is exactly what lets us construct this scenario to test the check.
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()
    session.add(
        FareQuote(
            route_id=9999,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=7,
            search_date=dt.datetime(2026, 9, 4),
            travel_date=dt.datetime(2026, 9, 11),
            total_fare=7000,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    session.commit()

    result = validate_data(session)
    check = _find(result, "orphaned_fare_quotes")
    assert check["ok"] is False
    assert "1 with a missing route" in check["detail"]


def test_validate_data_flags_a_stuck_running_scrape(session):
    session.add(
        ScrapeRun(
            started_at=dt.datetime.utcnow() - dt.timedelta(hours=5),
            status="running",
            quotes_collected=0,
        )
    )
    session.commit()

    result = validate_data(session)
    check = _find(result, "stuck_running_scrape_runs")
    assert check["ok"] is False


def test_validate_data_reports_recorded_failures_as_informational_not_a_failure(session):
    session.add(
        ScrapeRun(
            started_at=dt.datetime.utcnow(),
            finished_at=dt.datetime.utcnow(),
            status="error",
            quotes_collected=0,
            notes="FATAL: simulated",
        )
    )
    session.commit()

    result = validate_data(session)
    check = _find(result, "recorded_failed_runs")
    assert check["ok"] is True  # a recorded failure is the fix working, not a problem with the checker
    assert "1 run(s)" in check["detail"]
    assert result["all_ok"] is True
