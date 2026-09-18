from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.roles import ROLE_CITIZEN, ROLE_OPERATOR, ROLE_REGULATOR
from app.auth.service import create_user
from app.db.models import Base, Carrier, FareQuote, RegulatorFareFlag, Route

NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"

REGULATOR = ("dgca.officer", "regulator-pass-1")
OPERATOR_SG = ("spicejet.ops", "operator-pass-1")
OPERATOR_QP = ("akasa.ops", "operator-pass-2")
TRAVELLER = ("traveller", "traveller-pass-1")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    seed = TestSession()
    route = Route(origin="DEL", destination="BOM", display_name="Delhi-Mumbai")
    seed.add(route)
    seed.add(Carrier(code="SG", name="SpiceJet"))
    seed.add(Carrier(code="QP", name="Akasa Air"))
    seed.commit()

    create_user(
        seed, username=REGULATOR[0], password=REGULATOR[1], role=ROLE_REGULATOR,
        display_name="Tariff Monitoring Desk",
    )
    create_user(
        seed, username=OPERATOR_SG[0], password=OPERATOR_SG[1], role=ROLE_OPERATOR,
        carrier_code="SG",
    )
    create_user(
        seed, username=OPERATOR_QP[0], password=OPERATOR_QP[1], role=ROLE_OPERATOR,
        carrier_code="QP",
    )
    create_user(seed, username=TRAVELLER[0], password=TRAVELLER[1], role=ROLE_CITIZEN)
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


def _auth(client, account) -> dict[str, str]:
    username, password = account
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _flag_id(client) -> int:
    return client.get("/api/regulator/flags", headers=_auth(client, REGULATOR)).json()[0]["id"]


def test_flags_are_not_public(client):
    """A flag names a carrier, a route and a date. Published openly it reads
    as an accusation whatever it is labelled, so the queue does not leave the
    regulator's desk — an airline cannot read it here either, only its own
    flags via the operator surface."""
    assert client.get("/api/regulator/flags").status_code == 401
    assert client.get("/api/regulator/flags/1").status_code == 401
    assert (
        client.get("/api/regulator/flags", headers=_auth(client, OPERATOR_SG)).status_code == 403
    )
    assert (
        client.get("/api/regulator/flags/1", headers=_auth(client, OPERATOR_SG)).status_code == 403
    )


def test_flags_listing_is_visible_to_a_regulator(client):
    resp = client.get("/api/regulator/flags", headers=_auth(client, REGULATOR))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["carrier_name"] == "SpiceJet"
    assert body[0]["route"] == "Delhi-Mumbai"
    assert body[0]["status"] == "new"


def test_flag_detail_includes_real_possible_factors(client):
    resp = client.get(
        f"/api/regulator/flags/{_flag_id(client)}", headers=_auth(client, REGULATOR)
    )
    assert resp.status_code == 200
    types = {f["factor_type"] for f in resp.json()["possible_factors"]}
    assert "carrier_financial_context" in types


def test_flag_detail_404s_for_an_unknown_id(client):
    assert (
        client.get("/api/regulator/flags/9999", headers=_auth(client, REGULATOR)).status_code == 404
    )


def test_review_is_401_when_signed_out(client):
    resp = client.patch(f"/api/regulator/flags/{_flag_id(client)}/review", json={"status": "reviewed"})
    assert resp.status_code == 401


def test_review_is_403_for_an_airline(client):
    """An airline is authenticated here — the refusal is about role, not
    identity, so it must be 403 rather than 401."""
    resp = client.patch(
        f"/api/regulator/flags/{_flag_id(client)}/review",
        json={"status": "reviewed"},
        headers=_auth(client, OPERATOR_SG),
    )
    assert resp.status_code == 403


def test_review_records_the_signed_in_reviewer(client):
    resp = client.patch(
        f"/api/regulator/flags/{_flag_id(client)}/review",
        json={"status": "dismissed", "review_note": "Diwali week"},
        headers=_auth(client, REGULATOR),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dismissed"
    assert body["review_note"] == "Diwali week"
    assert body["reviewed_at"] is not None
    # Identity comes from the session, not the request body.
    assert body["reviewed_by"] == REGULATOR[0]


def test_review_ignores_a_reviewed_by_supplied_by_the_caller(client):
    """Attributing a decision to someone else would make the audit trail
    actively misleading, which is worse than having none."""
    resp = client.patch(
        f"/api/regulator/flags/{_flag_id(client)}/review",
        json={"status": "reviewed", "reviewed_by": "somebody.else"},
        headers=_auth(client, REGULATOR),
    )
    assert resp.status_code == 200
    assert resp.json()["reviewed_by"] == REGULATOR[0]


def test_review_rejects_a_status_outside_the_allowed_set(client):
    headers = _auth(client, REGULATOR)
    flag_id = _flag_id(client)
    # "sent" must never be an accepted state — nothing here sends anything.
    for bad in ("sent", "issued", "new", "whatever"):
        resp = client.patch(
            f"/api/regulator/flags/{flag_id}/review", json={"status": bad}, headers=headers
        )
        assert resp.status_code == 422, f"status {bad!r} should be rejected"


def test_draft_notice_is_gated_to_regulators(client):
    flag_id = _flag_id(client)
    assert client.get(f"/api/regulator/flags/{flag_id}/draft-notice").status_code == 401
    assert (
        client.get(
            f"/api/regulator/flags/{flag_id}/draft-notice", headers=_auth(client, OPERATOR_SG)
        ).status_code
        == 403
    )

    resp = client.get(
        f"/api/regulator/flags/{flag_id}/draft-notice", headers=_auth(client, REGULATOR)
    )
    assert resp.status_code == 200
    doc = resp.json()
    assert "DRAFT" in doc["draft_disclaimer"]
    assert doc["document_type"] == "DRAFT_FARE_REVIEW_NOTICE"


def test_citizen_report_submission_requires_an_account(client):
    """Reading is open; writing is not. An unauthenticated write endpoint
    feeding a human triage queue is an invitation to flood it."""
    assert (
        client.post(
            "/api/regulator/citizen-reports",
            json={
                "origin": "Delhi",
                "destination": "Patna",
                "travel_date": "2026-11-13",
                "reported_fare": 24000.0,
            },
        ).status_code
        == 401
    )


def test_a_signed_in_traveller_can_submit_a_report(client):
    resp = client.post(
        "/api/regulator/citizen-reports",
        headers=_auth(client, TRAVELLER),
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
        headers=_auth(client, TRAVELLER),
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
        headers=_auth(client, TRAVELLER),
        json={"origin": "  ", "destination": "Patna", "travel_date": "2026-11-13", "reported_fare": 9000.0},
    )
    assert resp.status_code == 422


def test_citizen_report_count_is_public_but_listing_is_gated(client):
    client.post(
        "/api/regulator/citizen-reports",
        headers=_auth(client, TRAVELLER),
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
    # so it must not be public — nor readable by the airlines being reported on.
    assert client.get("/api/regulator/citizen-reports").status_code == 401
    assert (
        client.get("/api/regulator/citizen-reports", headers=_auth(client, OPERATOR_SG)).status_code
        == 403
    )

    listed = client.get("/api/regulator/citizen-reports", headers=_auth(client, REGULATOR))
    assert listed.status_code == 200
    assert listed.json()[0]["contact_email"] == "someone@example.com"


def test_citizen_report_triage_records_the_review(client):
    report_id = client.post(
        "/api/regulator/citizen-reports",
        headers=_auth(client, TRAVELLER),
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
        headers=_auth(client, REGULATOR),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"
    assert resp.json()["reviewed_at"] is not None


def test_a_traveller_needs_no_account_for_the_public_surface(client):
    """The segregation runs both ways: the restricted surfaces are shut, and
    the public ones must stay genuinely open. A regression that quietly gated
    the index would be as wrong as one that leaked the flag queue."""
    public = [
        "/api/index/daily",
        "/api/routes",
        "/api/affordability",
        "/api/spike-watch",
        "/api/compliance",
        "/api/price-grid",
        "/api/regulator/citizen-reports/count",
    ]
    for path in public:
        assert client.get(path).status_code == 200, f"{path} must be open to everyone"

    # Submitting a report is the one traveller action that is NOT open —
    # see test_citizen_report_submission_requires_an_account for why.


def test_a_traveller_sees_only_their_own_reports(client):
    mine = _auth(client, TRAVELLER)
    client.post(
        "/api/regulator/citizen-reports",
        headers=mine,
        json={
            "origin": "Delhi",
            "destination": "Patna",
            "travel_date": "2026-11-13",
            "reported_fare": 24000.0,
        },
    )
    # Somebody else's report must not surface in the traveller's own list.
    client.post(
        "/api/regulator/citizen-reports",
        headers=_auth(client, REGULATOR),
        json={
            "origin": "Mumbai",
            "destination": "Goa",
            "travel_date": "2026-11-13",
            "reported_fare": 18000.0,
        },
    )

    resp = client.get("/api/citizen/my-reports", headers=mine)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["origin"] == "Delhi"

    assert client.get("/api/citizen/my-reports").status_code == 401
