from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Carrier, FareQuote, RegulatorFareFlag, Route
from app.regulator.auth import TOKEN_ENV_VAR

TOKEN = "test-regulator-token"
NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    seed = TestSession()
    route = Route(origin="DEL", destination="BOM", display_name="Delhi-Mumbai")
    seed.add(route)
    seed.add(Carrier(code="SG", name="SpiceJet"))
    seed.commit()

    flagged_day = dt.date(2026, 11, 1)
    quote = FareQuote(
        route_id=route.id,
        carrier_code="SG",
        source_id="spicejet",
        ap_window_days=7,
        search_date=dt.datetime.combine(flagged_day, dt.time.min),
        travel_date=dt.datetime.combine(flagged_day + dt.timedelta(days=7), dt.time.min),
        fare_class="economy",
        total_fare=21000.0,
        is_outlier=False,
        sold_out=False,
        scraped_at=dt.datetime.utcnow(),
    )
    seed.add(quote)
    seed.commit()
    seed.add(
        RegulatorFareFlag(
            route_id=route.id,
            carrier_code="SG",
            ap_window_days=7,
            flagged_search_date=dt.datetime.combine(flagged_day, dt.time.min),
            flagged_travel_date=dt.datetime.combine(flagged_day + dt.timedelta(days=7), dt.time.min),
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
    )
    seed.commit()
    seed.close()

    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", TestSession)
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

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c


def _auth(token=TOKEN):
    return {"X-Regulator-Token": token}


def test_flags_listing_is_public(client):
    resp = client.get("/api/regulator/flags")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["carrier_name"] == "SpiceJet"
    assert body[0]["route"] == "Delhi-Mumbai"
    assert body[0]["status"] == "new"


def test_flag_detail_includes_real_possible_factors(client):
    flag_id = client.get("/api/regulator/flags").json()[0]["id"]
    resp = client.get(f"/api/regulator/flags/{flag_id}")
    assert resp.status_code == 200
    types = {f["factor_type"] for f in resp.json()["possible_factors"]}
    assert "carrier_financial_context" in types


def test_flag_detail_404s_for_an_unknown_id(client):
    assert client.get("/api/regulator/flags/9999").status_code == 404


def test_review_is_gated_503_when_no_token_configured(client, monkeypatch):
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    flag_id = client.get("/api/regulator/flags").json()[0]["id"]
    resp = client.patch(f"/api/regulator/flags/{flag_id}/review", json={"status": "reviewed"})
    assert resp.status_code == 503


def test_review_is_gated_401_with_a_wrong_token(client, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, TOKEN)
    flag_id = client.get("/api/regulator/flags").json()[0]["id"]
    resp = client.patch(
        f"/api/regulator/flags/{flag_id}/review",
        json={"status": "reviewed"},
        headers=_auth("wrong"),
    )
    assert resp.status_code == 401


def test_review_records_the_decision_with_a_correct_token(client, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, TOKEN)
    flag_id = client.get("/api/regulator/flags").json()[0]["id"]
    resp = client.patch(
        f"/api/regulator/flags/{flag_id}/review",
        json={"status": "dismissed", "review_note": "Diwali week", "reviewed_by": "TMU desk"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dismissed"
    assert body["review_note"] == "Diwali week"
    assert body["reviewed_by"] == "TMU desk"
    assert body["reviewed_at"] is not None


def test_review_rejects_a_status_outside_the_allowed_set(client, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, TOKEN)
    flag_id = client.get("/api/regulator/flags").json()[0]["id"]
    # "sent" must never be an accepted state — nothing here sends anything.
    for bad in ("sent", "issued", "new", "whatever"):
        resp = client.patch(
            f"/api/regulator/flags/{flag_id}/review", json={"status": bad}, headers=_auth()
        )
        assert resp.status_code == 422, f"status {bad!r} should be rejected"


def test_draft_notice_is_gated_and_returns_the_draft_document(client, monkeypatch):
    flag_id = client.get("/api/regulator/flags").json()[0]["id"]

    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    assert client.get(f"/api/regulator/flags/{flag_id}/draft-notice").status_code == 503

    monkeypatch.setenv(TOKEN_ENV_VAR, TOKEN)
    assert client.get(f"/api/regulator/flags/{flag_id}/draft-notice").status_code == 401

    resp = client.get(f"/api/regulator/flags/{flag_id}/draft-notice", headers=_auth())
    assert resp.status_code == 200
    doc = resp.json()
    assert "DRAFT" in doc["draft_disclaimer"]
    assert doc["document_type"] == "DRAFT_FARE_REVIEW_NOTICE"


def test_citizen_report_submission_is_public(client):
    resp = client.post(
        "/api/regulator/citizen-reports",
        json={
            "origin": "Delhi",
            "destination": "Patna",
            "travel_date": "2026-11-13",
            "reported_fare": 24000.0,
            "note": "Chhath week, tripled overnight",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "new"


def test_citizen_report_rejects_an_implausible_fare(client):
    resp = client.post(
        "/api/regulator/citizen-reports",
        json={
            "origin": "Delhi",
            "destination": "Patna",
            "travel_date": "2026-11-13",
            "reported_fare": 9_999_999.0,
        },
    )
    assert resp.status_code == 422


def test_citizen_report_requires_origin_and_destination(client):
    resp = client.post(
        "/api/regulator/citizen-reports",
        json={"origin": "  ", "destination": "Patna", "travel_date": "2026-11-13", "reported_fare": 9000.0},
    )
    assert resp.status_code == 422


def test_citizen_report_count_is_public_but_listing_is_gated(client, monkeypatch):
    client.post(
        "/api/regulator/citizen-reports",
        json={
            "origin": "Delhi",
            "destination": "Patna",
            "travel_date": "2026-11-13",
            "reported_fare": 24000.0,
            "contact_email": "someone@example.com",
        },
    )

    count = client.get("/api/regulator/citizen-reports/count")
    assert count.status_code == 200
    assert count.json()["total"] == 1
    assert count.json()["new"] == 1

    # The raw list carries an optional contact email and unverified claims,
    # so it must not be public.
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)
    assert client.get("/api/regulator/citizen-reports").status_code == 503
    monkeypatch.setenv(TOKEN_ENV_VAR, TOKEN)
    assert client.get("/api/regulator/citizen-reports").status_code == 401

    listed = client.get("/api/regulator/citizen-reports", headers=_auth())
    assert listed.status_code == 200
    assert listed.json()[0]["contact_email"] == "someone@example.com"


def test_citizen_report_triage_records_the_review(client, monkeypatch):
    monkeypatch.setenv(TOKEN_ENV_VAR, TOKEN)
    report_id = client.post(
        "/api/regulator/citizen-reports",
        json={
            "origin": "Delhi",
            "destination": "Patna",
            "travel_date": "2026-11-13",
            "reported_fare": 24000.0,
        },
    ).json()["id"]

    resp = client.patch(
        f"/api/regulator/citizen-reports/{report_id}/review",
        json={"status": "reviewed", "reviewer_note": "matches a real flag"},
        headers=_auth(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"
    assert resp.json()["reviewed_at"] is not None
