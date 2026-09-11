from __future__ import annotations

import datetime as dt

from app.config import MOSPI_CPI_REFERENCE
from app.db.models import IndexValue
from app.index.cpi_divergence import cpi_divergence


def _add_index_value(session, date, value, sample_size=4, routes_covered=4):
    session.add(
        IndexValue(
            date=dt.datetime.combine(date, dt.time.min),
            frequency="daily",
            method="fisher",
            value=value,
            sample_size=sample_size,
            routes_covered=routes_covered,
            computed_at=dt.datetime.utcnow(),
        )
    )
    session.commit()


def test_cpi_divergence_no_signal_with_one_day(session):
    _add_index_value(session, dt.date(2026, 9, 4), 100.0)
    result = cpi_divergence(session)
    assert result["has_signal"] is False
    assert result["alert"] is False
    assert result["mospi"]["reference_month_label"] == MOSPI_CPI_REFERENCE.reference_month_label


def test_cpi_divergence_alerts_when_apix_move_exceeds_official_yoy(session):
    # a real move like the one actually observed this session: 100 -> 91.2
    # over a handful of days, an 8.8% swing that already exceeds the
    # official Passenger Transport Services CPI's entire year-on-year move
    _add_index_value(session, dt.date(2026, 9, 4), 100.0)
    _add_index_value(session, dt.date(2026, 9, 9), 91.2)
    result = cpi_divergence(session)
    assert result["has_signal"] is True
    assert result["alert"] is True
    assert result["apix_days_tracked"] == 5
    assert abs(result["apix_change_pct"] - (-8.8)) < 0.01
    assert result["ratio_vs_official_yoy"] > 1.0
    assert "already more than" in result["message"]


def test_cpi_divergence_no_alert_for_a_small_move(session):
    _add_index_value(session, dt.date(2026, 9, 4), 100.0)
    _add_index_value(session, dt.date(2026, 9, 5), 100.5)  # well below the 2.90% official YoY
    result = cpi_divergence(session)
    assert result["has_signal"] is True
    assert result["alert"] is False
    assert result["ratio_vs_official_yoy"] < 1.0
    assert "versus" in result["message"]


def test_cpi_divergence_reports_real_mospi_reference_figures(session):
    _add_index_value(session, dt.date(2026, 9, 4), 100.0)
    _add_index_value(session, dt.date(2026, 9, 9), 91.2)
    result = cpi_divergence(session)
    mospi = result["mospi"]
    assert mospi["passenger_transport_yoy_pct"] == 2.90
    assert mospi["series_base"] == "2024=100"
    assert mospi["source_url"].startswith("https://www.mospi.gov.in/")
