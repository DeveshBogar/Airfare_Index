from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Carrier, FareQuote, Route


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # isolate the API tests from the real dev database
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    seed = TestSession()
    route = Route(origin="DEL", destination="BOM", display_name="Delhi-Mumbai")
    seed.add(route)
    seed.add(Carrier(code="SG", name="SpiceJet"))
    seed.commit()
    seed.add(
        FareQuote(
            route_id=route.id,
            carrier_code="SG",
            source_id="spicejet",
            ap_window_days=7,
            search_date=dt.datetime(2026, 9, 4),
            travel_date=dt.datetime(2026, 9, 11),
            fare_class="economy",
            total_fare=7085.0,
            is_outlier=False,
            sold_out=False,
            scraped_at=dt.datetime.utcnow(),
        )
    )
    seed.commit()
    seed.close()

    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", TestSession)

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_routes_endpoint_returns_seeded_route(client):
    resp = client.get("/api/routes")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["origin"] == "DEL"
    assert body[0]["destination"] == "BOM"


def test_fares_endpoint_returns_seeded_quote(client):
    resp = client.get("/api/fares")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["total_fare"] == 7085.0
    assert body[0]["source_id"] == "spicejet"


def test_fares_endpoint_filters_by_origin(client):
    resp = client.get("/api/fares?origin=BLR")
    assert resp.status_code == 200
    assert resp.json() == []


def test_compliance_endpoint_lists_all_registered_sources(client):
    resp = client.get("/api/compliance")
    assert resp.status_code == 200
    body = resp.json()
    source_ids = {row["source_id"] for row in body}
    assert "spicejet" in source_ids
    assert "ixigo" in source_ids
    assert all(row["allowed"] is None for row in body)  # no scrape cycle has run yet


def test_index_daily_empty_before_construction(client):
    resp = client.get("/api/index/daily")
    assert resp.status_code == 200
    assert resp.json() == []


def test_index_backtest_reports_zero_days_honestly(client):
    resp = client.get("/api/index/backtest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days_available"] == 0
    assert body["target_days"] == 30
    assert body["status"] == "accumulating"


def test_elasticity_endpoint_ok(client):
    resp = client.get("/api/elasticity")
    assert resp.status_code == 200


def test_coverage_endpoint_reflects_seeded_data(client):
    resp = client.get("/api/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cells_with_data"] == 1  # DEL-BOM T+7, the one row seeded
    assert body["total_cells"] == body["routes_in_basket"] * len(body["ap_windows"])
    assert 0 < body["coverage_pct"] < 100
    assert "spicejet" in body["sources_contributing"]
    assert "DEL-BOM T+7" not in body["missing_cells"]


def test_heatmap_endpoint_ok(client):
    resp = client.get("/api/heatmap")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["route"] == "Delhi-Mumbai"
    assert body[0]["ap_window_days"] == 7


def test_date_watch_endpoint_finds_the_seeded_quote(client):
    route_id = client.get("/api/routes").json()[0]["id"]
    resp = client.get(f"/api/date-watch?route_id={route_id}&travel_date=2026-09-11")
    assert resp.status_code == 200
    body = resp.json()
    assert body["travel_date"] == "2026-09-11"
    checkpoint_7 = next(c for c in body["checkpoints"] if c["ap_window_days"] == 7)
    assert checkpoint_7["status"] == "collected"
    assert checkpoint_7["mean_fare"] == 7085.0


def test_date_watch_endpoint_rejects_a_past_travel_date(client):
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    resp = client.get(f"/api/date-watch?route_id=1&travel_date={yesterday}")
    assert resp.status_code == 400


def test_index_by_carrier_endpoint_ok_before_any_carrier_index_is_built(client):
    # No CarrierIndexValue rows exist yet in this fresh test DB -> the
    # endpoint should respond with empty series, not error.
    resp = client.get("/api/index/by-carrier")
    assert resp.status_code == 200
    body = resp.json()
    assert body["headline"] == []
    assert body["carriers"] == []


def test_carriers_financial_context_endpoint_covers_every_known_carrier(client, monkeypatch):
    monkeypatch.setattr(
        "app.scraper.compliance.requests.get",
        lambda *a, **k: type("R", (), {"status_code": 200, "text": "User-agent: *\nAllow: /\n"})(),
    )
    resp = client.get("/api/carriers/financial-context")
    assert resp.status_code == 200
    body = resp.json()
    by_code = {row["carrier_code"]: row for row in body}
    assert by_code["SG"]["available"] is True
    assert len(by_code["SG"]["quarters"]) > 0
    assert by_code["SG"]["carrier_name"] == "SpiceJet"
    assert by_code["QP"]["available"] is False
    assert "privately held" in by_code["QP"]["reason"].lower()
