from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import AP_WINDOWS, ROUTE_BASKET, SOURCE_REGISTRY
from app.db.models import ComplianceLog, FareQuote, Route, RouteWeight
from app.db.session import get_session
from app.index.affordability import basket_affordability
from app.index.spike_watch import basket_spike_watch, festival_route_prices
from app.schemas import AffordabilityReportOut, ComplianceStatusOut, FestivalRoutePricesOut, RouteOut, SpikeWatchOut

router = APIRouter(prefix="/api", tags=["routes"])


def _session():
    with get_session() as session:
        yield session


@router.get("/routes", response_model=list[RouteOut])
def list_routes(session: Session = Depends(_session)) -> list[RouteOut]:
    routes = session.execute(select(Route)).scalars().all()
    out = []
    for r in routes:
        latest = (
            session.execute(
                select(RouteWeight).where(RouteWeight.route_id == r.id).order_by(RouteWeight.as_of.desc())
            )
            .scalars()
            .first()
        )
        out.append(
            RouteOut(
                id=r.id,
                origin=r.origin,
                destination=r.destination,
                display_name=r.display_name,
                latest_weight=latest.weight if latest else None,
            )
        )
    return out


@router.get("/compliance", response_model=list[ComplianceStatusOut])
def compliance_status(session: Session = Depends(_session)) -> list[ComplianceStatusOut]:
    """Per-source live compliance status — which sources are actually
    allowed to run right now, and why, straight from the audit trail the
    compliance gate writes on every scrape cycle."""
    out = []
    for source_id, info in SOURCE_REGISTRY.items():
        latest_logs = (
            session.execute(
                select(ComplianceLog)
                .where(ComplianceLog.source_id == source_id)
                .order_by(ComplianceLog.checked_at.desc())
            )
            .scalars()
            .all()
        )
        if not latest_logs:
            out.append(
                ComplianceStatusOut(
                    source_id=source_id,
                    name=info.name,
                    kind=info.kind,
                    domain=info.domain,
                    allowed=None,
                    reason="not yet checked — run a scrape cycle",
                    checked_at=None,
                )
            )
            continue
        # most recent check per path, then AND them together
        seen_paths: dict[str, ComplianceLog] = {}
        for log in latest_logs:
            seen_paths.setdefault(log.path_checked, log)
        allowed = all(log.allowed for log in seen_paths.values())
        reason = "; ".join(f"{log.path_checked}: {log.reason}" for log in seen_paths.values())
        out.append(
            ComplianceStatusOut(
                source_id=source_id,
                name=info.name,
                kind=info.kind,
                domain=info.domain,
                allowed=allowed,
                reason=reason,
                checked_at=max(log.checked_at for log in seen_paths.values()),
            )
        )
    return out


@router.get("/spike-watch", response_model=SpikeWatchOut)
def spike_watch(session: Session = Depends(_session)) -> SpikeWatchOut:
    """Known Indian festival/wedding-season travel-demand windows, plus any
    routes where real scraped fares already show a measurable difference
    for travel dates inside one of those windows vs. this route's other
    dates. See app.index.spike_watch for the comparison methodology and
    app.config.TRAVEL_SPIKE_WINDOWS for the sourced calendar dates."""
    today = dt.date.today()
    horizon_end = today + dt.timedelta(days=max(AP_WINDOWS))
    return SpikeWatchOut(**basket_spike_watch(session, as_of=today, horizon_end=horizon_end))


@router.get("/spike-watch/{window_key}/prices", response_model=FestivalRoutePricesOut)
def spike_watch_route_prices(window_key: str, session: Session = Depends(_session)) -> FestivalRoutePricesOut:
    """Every basket route's price for one specific festival/wedding-season
    window - real where we've collected fares with a travel date inside
    it, a clearly-flagged estimate otherwise. See
    app.index.spike_watch.festival_route_prices for the methodology."""
    result = festival_route_prices(session, window_key)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown window_key: {window_key}")
    return FestivalRoutePricesOut(**result)


@router.get("/affordability", response_model=AffordabilityReportOut)
def affordability(session: Session = Depends(_session)) -> AffordabilityReportOut:
    """Real fares normalized against real distance (cost per km) and real
    wages (days of a casual labourer's daily wage) — see
    app.index.affordability for the methodology and app.config.
    AIRPORT_COORDINATES / WAGE_REFERENCE for the sourced reference data."""
    return AffordabilityReportOut(**basket_affordability(session))


@router.get("/coverage")
def coverage(session: Session = Depends(_session)) -> dict:
    """How much of the (route x advance-purchase-window) basket actually
    has real data right now, and from which sources — makes gaps visible
    instead of a dashboard that looks complete when it isn't. This is
    honest by construction: it counts real fare_quotes rows, it doesn't
    infer or interpolate anything."""
    total_cells = len(ROUTE_BASKET) * len(AP_WINDOWS)

    rows = session.execute(
        select(Route.origin, Route.destination, FareQuote.ap_window_days, FareQuote.source_id)
        .join(Route, FareQuote.route_id == Route.id)
        .where(FareQuote.total_fare.is_not(None), FareQuote.is_outlier.is_(False))
    ).all()

    covered_cells: set[tuple[str, str, int]] = set()
    sources_seen: set[str] = set()
    for origin, destination, ap_days, source_id in rows:
        covered_cells.add((origin, destination, ap_days))
        sources_seen.add(source_id)

    basket_set = set(ROUTE_BASKET)
    covered_in_basket = {
        (o, d, w) for (o, d, w) in covered_cells if (o, d) in basket_set or (d, o) in basket_set
    }

    return {
        "routes_in_basket": len(ROUTE_BASKET),
        "ap_windows": AP_WINDOWS,
        "total_cells": total_cells,
        "cells_with_data": len(covered_in_basket),
        "coverage_pct": round(100 * len(covered_in_basket) / total_cells, 1) if total_cells else 0.0,
        "sources_contributing": sorted(sources_seen),
        "missing_cells": sorted(
            f"{o}-{d} T+{w}"
            for (o, d) in ROUTE_BASKET
            for w in AP_WINDOWS
            if (o, d, w) not in covered_in_basket and (d, o, w) not in covered_in_basket
        ),
    }
