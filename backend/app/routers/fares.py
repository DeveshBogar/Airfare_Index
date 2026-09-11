from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FareQuote, Route
from app.db.session import get_session
from app.index.booking_advice import booking_advice
from app.index.date_watch import date_watch
from app.index.elasticity import lead_time_curve
from app.index.estimation import basket_price_grid
from app.index.price_history import route_price_history
from app.schemas import (
    BookingAdviceOut,
    DateWatchOut,
    ElasticityPointOut,
    FareQuoteOut,
    PriceGridOut,
    RoutePriceHistoryOut,
)

router = APIRouter(prefix="/api", tags=["fares"])


def _session():
    with get_session() as session:
        yield session


@router.get("/fares", response_model=list[FareQuoteOut])
def list_fares(
    origin: str | None = None,
    destination: str | None = None,
    ap_window_days: int | None = None,
    source_id: str | None = None,
    include_outliers: bool = False,
    limit: int = Query(500, le=5000),
    session: Session = Depends(_session),
) -> list[FareQuoteOut]:
    query = select(FareQuote, Route).join(Route, FareQuote.route_id == Route.id)
    if origin:
        query = query.where(Route.origin == origin.upper())
    if destination:
        query = query.where(Route.destination == destination.upper())
    if ap_window_days is not None:
        query = query.where(FareQuote.ap_window_days == ap_window_days)
    if source_id:
        query = query.where(FareQuote.source_id == source_id)
    if not include_outliers:
        query = query.where(FareQuote.is_outlier.is_(False))
    query = query.order_by(FareQuote.scraped_at.desc()).limit(limit)

    rows = session.execute(query).all()
    return [
        FareQuoteOut(
            id=fq.id,
            route=route.display_name,
            carrier_code=fq.carrier_code,
            source_id=fq.source_id,
            ap_window_days=fq.ap_window_days,
            search_date=fq.search_date.date(),
            travel_date=fq.travel_date.date(),
            fare_class=fq.fare_class,
            base_fare=fq.base_fare,
            taxes_fees=fq.taxes_fees,
            total_fare=fq.total_fare,
            is_outlier=fq.is_outlier,
            sold_out=fq.sold_out,
        )
        for fq, route in rows
    ]


@router.get("/elasticity", response_model=list[ElasticityPointOut])
def elasticity(route_id: int | None = None, session: Session = Depends(_session)) -> list[ElasticityPointOut]:
    curve = lead_time_curve(session, route_id=route_id)
    return [ElasticityPointOut(**point) for point in curve]


@router.get("/booking-advice", response_model=BookingAdviceOut)
def booking_advice_endpoint(route_id: int, session: Session = Depends(_session)) -> BookingAdviceOut:
    """Plain-language 'best time to book' verdict for one route, derived
    from its real lead-time elasticity curve — see app.index.booking_advice
    for the reasoning."""
    return BookingAdviceOut(**booking_advice(session, route_id=route_id))


@router.get("/date-watch", response_model=DateWatchOut)
def date_watch_endpoint(
    route_id: int, travel_date: dt.date, session: Session = Depends(_session)
) -> DateWatchOut:
    """Real prices collected so far for one exact travel date on one
    route, grouped by how many days before departure they were booked -
    lets a traveller with a specific trip in mind see the cheapest real
    price found for that date and which booking-lead-time checkpoints are
    still pending. See app.index.date_watch for the methodology."""
    today = dt.date.today()
    if travel_date < today:
        raise HTTPException(status_code=400, detail="travel_date must be today or in the future")
    return DateWatchOut(**date_watch(session, route_id=route_id, travel_date=travel_date, today=today))


@router.get("/price-history", response_model=RoutePriceHistoryOut)
def price_history_endpoint(route_id: int, session: Session = Depends(_session)) -> RoutePriceHistoryOut:
    """Real day-by-day fare history for one route, straight from scraped
    FareQuote rows grouped by the calendar day we searched - nothing
    estimated or backfilled. See app.index.price_history for the
    methodology (including the small-sample caveat on typical_low/high
    while real history is still thin)."""
    result = route_price_history(session, route_id=route_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown route_id: {route_id}")
    return RoutePriceHistoryOut(**result)


@router.get("/heatmap")
def sector_heatmap(session: Session = Depends(_session)) -> list[dict]:
    """Mean cheapest fare per route/AP-window cell — powers the dashboard's
    sector-wise heatmap."""
    rows = session.execute(
        select(
            Route.display_name,
            FareQuote.ap_window_days,
            FareQuote.total_fare,
        )
        .join(Route, FareQuote.route_id == Route.id)
        .where(FareQuote.is_outlier.is_(False), FareQuote.sold_out.is_(False), FareQuote.total_fare.is_not(None))
    ).all()

    cells: dict[tuple[str, int], list[float]] = {}
    for display_name, ap_days, total_fare in rows:
        cells.setdefault((display_name, ap_days), []).append(total_fare)

    return [
        {
            "route": route,
            "ap_window_days": ap_days,
            "mean_fare": sum(values) / len(values),
            "min_fare": min(values),
            "sample_size": len(values),
        }
        for (route, ap_days), values in cells.items()
    ]


@router.get("/price-grid", response_model=PriceGridOut)
def price_grid(session: Session = Depends(_session)) -> PriceGridOut:
    """Every (route, AP-window) cell in the basket, real fares where we
    have them and clearly-flagged estimates where we don't — see
    app.index.estimation for the methodology. The real index (/api/index/
    daily) never uses these estimates; this endpoint is display-only."""
    return PriceGridOut(**basket_price_grid(session))
