from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.run_backtest import backtest_report
from app.db.models import Carrier, CarrierIndexValue, IndexValue
from app.db.session import get_session
from app.index.cpi_divergence import cpi_divergence
from app.schemas import (
    ByCarrierIndexOut,
    CarrierIndexPointOut,
    CarrierIndexSeriesOut,
    CpiDivergenceOut,
    IndexPointOut,
)

router = APIRouter(prefix="/api", tags=["index"])


def _session():
    with get_session() as session:
        yield session


@router.get("/index/daily")
def index_daily(session: Session = Depends(_session)) -> list[dict]:
    rows = (
        session.execute(select(IndexValue).where(IndexValue.frequency == "daily").order_by(IndexValue.date))
        .scalars()
        .all()
    )
    by_date: dict[str, dict] = {}
    for r in rows:
        key = r.date.date().isoformat()
        entry = by_date.setdefault(
            key, {"date": key, "sample_size": r.sample_size, "routes_covered": r.routes_covered}
        )
        entry[r.method] = round(r.value, 3)
    return list(by_date.values())


@router.get("/index/backtest")
def index_backtest(method: str = "fisher", session: Session = Depends(_session)) -> dict:
    return backtest_report(session, method=method)


@router.get("/index/cpi-divergence", response_model=CpiDivergenceOut)
def index_cpi_divergence(session: Session = Depends(_session)) -> CpiDivergenceOut:
    """Compares APIx's real, tracked movement against the last officially
    published MoSPI CPI figure for the closest matching category — see
    app.index.cpi_divergence for the methodology and app.config.
    MOSPI_CPI_REFERENCE for the sourced official figures."""
    return CpiDivergenceOut(**cpi_divergence(session))


@router.get("/index/by-carrier", response_model=ByCarrierIndexOut)
def index_by_carrier(session: Session = Depends(_session)) -> ByCarrierIndexOut:
    """Each carrier's own daily index (Laspeyres/Paasche/Fisher, scoped to
    that carrier's own fares) alongside the same whole-market headline
    series /index/daily serves — see app.index.carrier_index for the
    construction and what `carrier_weight` does and does not mean."""
    headline_rows = (
        session.execute(select(IndexValue).where(IndexValue.frequency == "daily").order_by(IndexValue.date))
        .scalars()
        .all()
    )
    headline_by_date: dict[str, dict] = {}
    for r in headline_rows:
        key = r.date.date().isoformat()
        entry = headline_by_date.setdefault(
            key, {"date": r.date.date(), "sample_size": r.sample_size, "routes_covered": r.routes_covered}
        )
        entry[r.method] = round(r.value, 3)
    headline = [IndexPointOut(**row) for row in headline_by_date.values() if "fisher" in row]

    carrier_rows = (
        session.execute(
            select(CarrierIndexValue)
            .where(CarrierIndexValue.frequency == "daily")
            .order_by(CarrierIndexValue.carrier_code, CarrierIndexValue.date)
        )
        .scalars()
        .all()
    )
    carrier_names = {c.code: c.name for c in session.execute(select(Carrier)).scalars().all()}

    by_carrier: dict[str, dict[str, dict]] = {}
    weight_by_carrier: dict[str, float] = {}
    for r in carrier_rows:
        key = r.date.date().isoformat()
        points = by_carrier.setdefault(r.carrier_code, {})
        entry = points.setdefault(
            key, {"date": r.date.date(), "sample_size": r.sample_size, "routes_covered": r.routes_covered}
        )
        entry[r.method] = round(r.value, 3)
        weight_by_carrier[r.carrier_code] = r.carrier_weight  # constant per carrier; last write wins

    carriers = [
        CarrierIndexSeriesOut(
            carrier_code=carrier_code,
            carrier_name=carrier_names.get(carrier_code, carrier_code),
            carrier_weight=weight_by_carrier.get(carrier_code, 0.0),
            points=[CarrierIndexPointOut(**row) for row in points.values() if "fisher" in row],
        )
        for carrier_code, points in sorted(by_carrier.items())
    ]

    return ByCarrierIndexOut(headline=headline, carriers=carriers)
