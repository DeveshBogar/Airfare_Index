"""The operator surface's whole security property is that an airline sees
its own carrier and nothing else. These tests exercise that boundary from
the outside, with two carriers seeded so "scoped correctly" and "returns
everything" cannot look the same.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.roles import ROLE_OPERATOR, ROLE_REGULATOR
from app.auth.service import create_user
from app.db.models import Base, Carrier, FareQuote, RegulatorFareFlag, Route

NO_ROBOTS_RESTRICTION = "User-agent: *\nAllow: /\n"

SPICEJET = ("spicejet.ops", "operator-pass-1")
AKASA = ("akasa.ops", "operator-pass-2")
REGULATOR = ("dgca.officer", "regulator-pass-1")

FLAG_DAY = dt.date(2026, 11, 1)


def _flag(route_id: int, carrier_code: str, fare: float) -> RegulatorFareFlag:
    return RegulatorFareFlag(
        route_id=route_id,
        carrier_code=carrier_code,
        ap_window_days=7,
        flagged_search_date=dt.datetime.combine(FLAG_DAY, dt.time.min),
        flagged_travel_date=dt.datetime.combine(FLAG_DAY + dt.timedelta(days=7), dt.time.min),
        observed_fare=fare,
        baseline_median_fare=7025.0,
        baseline_mad=75.0,
        robust_z_score=125.6,
        pct_above_baseline_median=198.9,
        baseline_sample_size=4,
        status="new",
        detected_at=dt.datetime.utcnow(),
    )


def _quote(route_id: int, carrier_code: str, fare: float) -> FareQuote:
    return FareQuote(
        route_id=route_id,
        carrier_code=carrier_code,
        source_id=carrier_code.lower(),
        ap_window_days=7,
        search_date=dt.datetime.combine(FLAG_DAY, dt.time.min),
        travel_date=dt.datetime.combine(FLAG_DAY + dt.timedelta(days=7), dt.time.min),
        fare_class="economy",
        total_fare=fare,
        is_outlier=False,
        sold_out=False,
        scraped_at=dt.datetime.utcnow(),
    )


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

    create_user(seed, username=SPICEJET[0], password=SPICEJET[1], role=ROLE_OPERATOR, carrier_code="SG")
    create_user(seed, username=AKASA[0], password=AKASA[1], role=ROLE_OPERATOR, carrier_code="QP")
    create_user(seed, username=REGULATOR[0], password=REGULATOR[1], role=ROLE_REGULATOR)

    seed.add(_quote(route.id, "SG", 21000.0))
    seed.add(_quote(route.id, "QP", 19500.0))
    seed.add(_flag(route.id, "SG", 21000.0))
    seed.add(_flag(route.id, "QP", 19500.0))
    seed.commit()
    seed.close()

    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", TestSession)
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": NO_ROBOTS_RESTRICTION})(),
    )

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c


def _auth(client, account) -> dict[str, str]:
    username, password = account
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_operator_endpoints_require_signing_in(client):
    for path in ("/api/operator/overview", "/api/operator/flags", "/api/operator/fares"):
        assert client.get(path).status_code == 401, path


def test_operator_endpoints_refuse_a_regulator(client):
    """A government account is authenticated but is not an airline — the
    refusal is about role, so it must be 403 rather than 401."""
    headers = _auth(client, REGULATOR)
    for path in ("/api/operator/overview", "/api/operator/flags", "/api/operator/fares"):
        assert client.get(path, headers=headers).status_code == 403, path


def test_overview_is_scoped_to_the_signed_in_carrier(client):
    body = client.get("/api/operator/overview", headers=_auth(client, SPICEJET)).json()
    assert body["carrier_code"] == "SG"
    assert body["carrier_name"] == "SpiceJet"
    assert body["quotes_collected"] == 1  # its own quote, not Akasa's
    assert body["flags_total"] == 1
    assert body["flags_awaiting_response"] == 1


def test_each_operator_sees_only_its_own_flags(client):
    spicejet = client.get("/api/operator/flags", headers=_auth(client, SPICEJET)).json()
    akasa = client.get("/api/operator/flags", headers=_auth(client, AKASA)).json()

    assert {f["carrier_code"] for f in spicejet} == {"SG"}
    assert {f["carrier_code"] for f in akasa} == {"QP"}
    assert spicejet[0]["id"] != akasa[0]["id"]


def test_each_operator_sees_only_its_own_fares(client):
    spicejet = client.get("/api/operator/fares", headers=_auth(client, SPICEJET)).json()
    akasa = client.get("/api/operator/fares", headers=_auth(client, AKASA)).json()

    assert {q["carrier_code"] for q in spicejet} == {"SG"}
    assert {q["carrier_code"] for q in akasa} == {"QP"}


def test_an_operator_can_respond_to_its_own_flag(client):
    headers = _auth(client, SPICEJET)
    flag_id = client.get("/api/operator/flags", headers=headers).json()[0]["id"]

    resp = client.post(
        f"/api/operator/flags/{flag_id}/response",
        json={"response": "Sole remaining fare bucket on a Diwali-week departure."},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["operator_response"].startswith("Sole remaining")
    assert body["operator_responded_by"] == SPICEJET[0]
    assert body["operator_responded_at"] is not None
    # Answering a flag is a right of reply, not the power to close it.
    assert body["status"] == "new"


def test_an_operator_cannot_respond_to_another_carriers_flag(client):
    akasa_flag_id = client.get("/api/operator/flags", headers=_auth(client, AKASA)).json()[0]["id"]

    resp = client.post(
        f"/api/operator/flags/{akasa_flag_id}/response",
        json={"response": "not mine to answer"},
        headers=_auth(client, SPICEJET),
    )
    # 404 rather than 403: a 403 would confirm the flag exists and let an
    # operator map competitors' flags by walking the id space.
    assert resp.status_code == 404


def test_an_empty_response_is_refused(client):
    headers = _auth(client, SPICEJET)
    flag_id = client.get("/api/operator/flags", headers=headers).json()[0]["id"]
    resp = client.post(
        f"/api/operator/flags/{flag_id}/response", json={"response": "   "}, headers=headers
    )
    assert resp.status_code == 422


def test_an_operator_response_is_visible_to_the_regulator(client):
    """The right of reply is worthless if the reviewer cannot see it."""
    operator_headers = _auth(client, SPICEJET)
    flag_id = client.get("/api/operator/flags", headers=operator_headers).json()[0]["id"]
    client.post(
        f"/api/operator/flags/{flag_id}/response",
        json={"response": "Fuel surcharge revision filed with DGCA on 2026-10-28."},
        headers=operator_headers,
    )

    seen = client.get(f"/api/regulator/flags/{flag_id}", headers=_auth(client, REGULATOR)).json()
    assert "Fuel surcharge revision" in seen["operator_response"]
    assert seen["operator_responded_by"] == SPICEJET[0]
