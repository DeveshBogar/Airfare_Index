from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtest.run_backtest import backtest_report
from app.db.models import IndexValue
from app.db.session import get_session
from app.index.cpi_divergence import cpi_divergence
from app.schemas import CpiDivergenceOut, IndexPointOut

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
