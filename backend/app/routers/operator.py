"""Airline-facing endpoints, scoped to the signed-in operator's own carrier.

Every query in this module filters on ``user.carrier_code`` taken from the
authenticated account — never from a query parameter. That is the whole
security property of this router, so it is worth being explicit about why
it is built this way:

  - **No carrier parameter exists anywhere here.** If an endpoint accepted
    ``?carrier_code=``, the scoping would depend on remembering to validate
    it on every single route, and one omission would expose a competitor's
    data. Taking it from the session makes the safe behaviour the only
    behaviour available.
  - **Another carrier's flag returns 404, not 403.** 403 would confirm that
    a flag with that id exists, letting an operator map out how many flags
    competitors have by walking the id space. 404 tells them nothing.
  - **Market-wide aggregates are included; per-competitor detail is not.**
    The headline index is already public, and an operator cannot interpret
    its own index movement without it. No endpoint here returns another
    carrier's fares or index series.

To be exact about what that last point does and does not claim: it is a
property of *this router*, not a claim that airlines cannot see each
other's numbers at all. The public dashboard publishes a per-carrier index
to everybody, and anyone can read it signed out — pretending otherwise
here would be security theatre. What the operator role adds is own-carrier
detail that is not public (fare-level rows, the flags raised against it)
plus the ability to answer those flags, and it is that private surface
which is scoped.

Operators can write exactly three columns on a flag (the response text, who
filed it, and when). They cannot change a flag's status, its review note,
or any measured value: answering a flag is a right of reply, not the
ability to close it.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import db_session, require_operator
from app.db.models import (
    Carrier,
    CarrierIndexValue,
    FareQuote,
    IndexValue,
    RegulatorFareFlag,
    User,
)
from app.regulator.views import carrier_names, flag_to_out
from app.schemas import (
    CarrierIndexPointOut,
    CarrierIndexSeriesOut,
    FareQuoteOut,
    IndexPointOut,
    OperatorFlagResponseIn,
    OperatorOverviewOut,
    RegulatorFlagOut,
)

router = APIRouter(prefix="/api/operator", tags=["operator"])

MAX_RESPONSE_CHARS = 4000


def _own_carrier_index(session: Session, carrier_code: str) -> CarrierIndexSeriesOut | None:
    rows = (
        session.execute(
            select(CarrierIndexValue)
            .where(
                CarrierIndexValue.carrier_code == carrier_code,
                CarrierIndexValue.frequency == "daily",
            )
            .order_by(CarrierIndexValue.date)
        )
        .scalars()
        .all()
    )
    if not rows:
        return None

    points: dict[str, dict] = {}
    weight = 0.0
    for row in rows:
        entry = points.setdefault(
            row.date.date().isoformat(),
            {
                "date": row.date.date(),
                "sample_size": row.sample_size,
                "routes_covered": row.routes_covered,
            },
        )
        entry[row.method] = round(row.value, 3)
        weight = row.carrier_weight

    carrier = session.get(Carrier, carrier_code)
    return CarrierIndexSeriesOut(
        carrier_code=carrier_code,
        carrier_name=carrier.name if carrier else carrier_code,
        carrier_weight=weight,
        # Only fully-computed days: a date missing Fisher means the
        # construction did not complete for it, and a partial point would
        # plot as a real movement.
        points=[CarrierIndexPointOut(**row) for row in points.values() if "fisher" in row],
    )


def _headline_series(session: Session) -> list[IndexPointOut]:
    rows = (
        session.execute(
            select(IndexValue).where(IndexValue.frequency == "daily").order_by(IndexValue.date)
        )
        .scalars()
        .all()
    )
    by_date: dict[str, dict] = {}
    for row in rows:
        entry = by_date.setdefault(
            row.date.date().isoformat(),
            {
                "date": row.date.date(),
                "sample_size": row.sample_size,
                "routes_covered": row.routes_covered,
            },
        )
        entry[row.method] = round(row.value, 3)
    return [IndexPointOut(**row) for row in by_date.values() if "fisher" in row]


@router.get("/overview", response_model=OperatorOverviewOut)
def operator_overview(
    user: User = Depends(require_operator), session: Session = Depends(db_session)
) -> OperatorOverviewOut:
    """One call backing the whole operator dashboard, for the signed-in
    airline's own carrier only."""
    carrier_code = user.carrier_code
    carrier = session.get(Carrier, carrier_code)
    series = _own_carrier_index(session, carrier_code)

    quotes_collected = (
        session.execute(
            select(func.count(FareQuote.id)).where(FareQuote.carrier_code == carrier_code)
        ).scalar_one()
        or 0
    )
    routes_covered = (
        session.execute(
            select(func.count(func.distinct(FareQuote.route_id))).where(
                FareQuote.carrier_code == carrier_code
            )
        ).scalar_one()
        or 0
    )

    flag_statuses = session.execute(
        select(RegulatorFareFlag.status, RegulatorFareFlag.operator_response).where(
            RegulatorFareFlag.carrier_code == carrier_code
        )
    ).all()

    latest_point = series.points[-1] if series and series.points else None

    return OperatorOverviewOut(
        carrier_code=carrier_code,
        carrier_name=carrier.name if carrier else carrier_code,
        index=series,
        headline=_headline_series(session),
        latest_index_value=latest_point.fisher if latest_point else None,
        latest_index_date=latest_point.date if latest_point else None,
        quotes_collected=quotes_collected,
        routes_covered=routes_covered,
        flags_total=len(flag_statuses),
        flags_new=sum(1 for status_value, _ in flag_statuses if status_value == "new"),
        flags_awaiting_response=sum(
            1 for status_value, response in flag_statuses
            if status_value != "dismissed" and not (response or "").strip()
        ),
    )


@router.get("/flags", response_model=list[RegulatorFlagOut])
def operator_flags(
    status_filter: str | None = None,
    user: User = Depends(require_operator),
    session: Session = Depends(db_session),
) -> list[RegulatorFlagOut]:
    """Flags raised against the signed-in airline, newest first."""
    query = (
        select(RegulatorFareFlag)
        .where(RegulatorFareFlag.carrier_code == user.carrier_code)
        .order_by(RegulatorFareFlag.flagged_search_date.desc(), RegulatorFareFlag.id.desc())
    )
    if status_filter:
        query = query.where(RegulatorFareFlag.status == status_filter)

    flags = session.execute(query).scalars().all()
    names = carrier_names(session)
    return [RegulatorFlagOut(**flag_to_out(f, names)) for f in flags]


@router.post("/flags/{flag_id}/response", response_model=RegulatorFlagOut)
def respond_to_flag(
    flag_id: int,
    body: OperatorFlagResponseIn,
    user: User = Depends(require_operator),
    session: Session = Depends(db_session),
) -> RegulatorFlagOut:
    """File the airline's written account of a flagged fare.

    Writes only the response columns. Status stays wherever the regulator
    left it — a carrier answering a flag does not resolve it, and letting
    an operator move a flag to "dismissed" would hand the subject of a
    review control over its outcome.
    """
    response = body.response.strip()
    if not response:
        raise HTTPException(status_code=422, detail="response text is required")
    if len(response) > MAX_RESPONSE_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"response must be at most {MAX_RESPONSE_CHARS} characters",
        )

    flag = session.get(RegulatorFareFlag, flag_id)
    # 404 rather than 403 when the flag belongs to another carrier: a 403
    # would confirm the flag exists, which is exactly what an operator
    # probing competitors' ids is trying to learn.
    if flag is None or flag.carrier_code != user.carrier_code:
        raise HTTPException(status_code=404, detail=f"no flag with id {flag_id} for your carrier")

    flag.operator_response = response
    flag.operator_responded_by = user.username
    flag.operator_responded_at = dt.datetime.utcnow()
    session.flush()
    return RegulatorFlagOut(**flag_to_out(flag, carrier_names(session)))


@router.get("/fares", response_model=list[FareQuoteOut])
def operator_fares(
    limit: int = 200,
    user: User = Depends(require_operator),
    session: Session = Depends(db_session),
) -> list[FareQuoteOut]:
    """The signed-in airline's own collected fares, most recent first."""
    capped = max(1, min(limit, 1000))
    quotes = (
        session.execute(
            select(FareQuote)
            .where(FareQuote.carrier_code == user.carrier_code)
            .order_by(FareQuote.search_date.desc(), FareQuote.id.desc())
            .limit(capped)
        )
        .scalars()
        .all()
    )
    return [
        FareQuoteOut(
            id=q.id,
            route=q.route.display_name if q.route else str(q.route_id),
            carrier_code=q.carrier_code,
            source_id=q.source_id,
            ap_window_days=q.ap_window_days,
            search_date=q.search_date.date(),
            travel_date=q.travel_date.date(),
            fare_class=q.fare_class,
            base_fare=q.base_fare,
            taxes_fees=q.taxes_fees,
            total_fare=q.total_fare,
            is_outlier=q.is_outlier,
            sold_out=q.sold_out,
        )
        for q in quotes
    ]
