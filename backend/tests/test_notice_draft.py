from __future__ import annotations

import datetime as dt

from app.db.models import Carrier, FareQuote, RegulatorFareFlag, Route
from app.regulator.notice_draft import DOCUMENT_TYPE, build_draft_notice

NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"


def _seed_flag(session, flagged_search_date=dt.date(2026, 11, 1), ap_days=7):
    route = Route(origin="DEL", destination="BOM", display_name="Delhi-Mumbai")
    session.add(route)
    session.add(Carrier(code="SG", name="SpiceJet"))
    session.commit()

    quote = FareQuote(
        route_id=route.id,
        carrier_code="SG",
        source_id="spicejet",
        ap_window_days=ap_days,
        search_date=dt.datetime.combine(flagged_search_date, dt.time.min),
        travel_date=dt.datetime.combine(flagged_search_date + dt.timedelta(days=ap_days), dt.time.min),
        fare_class="economy",
        total_fare=21000.0,
        is_outlier=False,
        sold_out=False,
        scraped_at=dt.datetime.utcnow(),
    )
    session.add(quote)
    session.commit()

    flag = RegulatorFareFlag(
        route_id=route.id,
        carrier_code="SG",
        ap_window_days=ap_days,
        flagged_search_date=dt.datetime.combine(flagged_search_date, dt.time.min),
        flagged_travel_date=dt.datetime.combine(flagged_search_date + dt.timedelta(days=ap_days), dt.time.min),
        fare_quote_id=quote.id,
        observed_fare=21000.0,
        baseline_median_fare=7025.0,
        baseline_mad=75.0,
        robust_z_score=125.6,
        pct_above_baseline_median=198.9,
        baseline_sample_size=4,
        status="new",
        detected_at=dt.datetime.utcnow(),
    )
    session.add(flag)
    session.commit()
    return flag


def _offline(monkeypatch):
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


def test_draft_notice_has_every_required_section(session, monkeypatch):
    _offline(monkeypatch)
    doc = build_draft_notice(session, _seed_flag(session))

    for key in (
        "document_type",
        "draft_disclaimer",
        "flag_id",
        "subject",
        "observation",
        "detection_method_note",
        "possible_factors",
        "regulator_review",
        "boundary_notice",
    ):
        assert key in doc, f"draft notice missing {key}"
    assert doc["document_type"] == DOCUMENT_TYPE


def test_disclaimer_is_unmissable_and_says_draft(session, monkeypatch):
    _offline(monkeypatch)
    doc = build_draft_notice(session, _seed_flag(session))
    disclaimer = doc["draft_disclaimer"]
    assert "DRAFT" in disclaimer
    assert "NOT AN OFFICIAL COMMUNICATION" in disclaimer
    # It must say out loud that it carries no authority and must not be sent as-is.
    assert "no legal or regulatory authority" in disclaimer
    assert "Must not be sent" in disclaimer


def test_boundary_notice_disclaims_any_finding_of_wrongdoing(session, monkeypatch):
    _offline(monkeypatch)
    doc = build_draft_notice(session, _seed_flag(session))
    boundary = doc["boundary_notice"].lower()
    assert "no finding" in boundary
    assert "issues nothing and sends nothing" in boundary


def test_observation_carries_the_real_stored_numbers(session, monkeypatch):
    _offline(monkeypatch)
    flag = _seed_flag(session)
    obs = build_draft_notice(session, flag)["observation"]
    assert obs["observed_fare_inr"] == 21000.0
    assert obs["baseline_median_fare_inr"] == 7025.0
    assert obs["baseline_sample_size"] == 4
    assert obs["robust_z_score"] == 125.6


def test_detection_method_note_states_the_actual_method_and_cites_its_source(session, monkeypatch):
    _offline(monkeypatch)
    note = build_draft_notice(session, _seed_flag(session))["detection_method_note"]
    assert "0.6745" in note
    assert "robust_outlier_mask" in note  # cites the function it reuses
    assert "never flagged" in note  # states the directional limitation


def test_possible_factors_are_real_and_include_the_festival_window_when_applicable(session, monkeypatch):
    _offline(monkeypatch)
    # 1 Nov 2026 search + 7-day window = 8 Nov travel, inside Diwali 2026.
    doc = build_draft_notice(session, _seed_flag(session, flagged_search_date=dt.date(2026, 11, 1)))
    types = {f["factor_type"] for f in doc["possible_factors"]}
    assert "festival_demand_window" in types
    assert "carrier_financial_context" in types
