"""Cleaning pipeline: dedupe -> outlier flagging -> fare decomposition ->
persist as FareQuote rows.

Outlier flagging uses a robust (median/MAD) z-score computed within each
(route, advance-purchase-window) group of a single scrape run, rather than
a plain mean/stdev, because airfare distributions are heavy-tailed by
construction (a handful of last-seats-on-the-plane prices next to a wall
of steady fares) — a couple of extreme genuine prices would blow out a
normal stdev and could wrongly flag ordinary fares. Flagged rows are kept
(not deleted) with is_outlier=True so they stay auditable and are simply
excluded from index construction by default.

Fare decomposition (base fare vs. taxes/fees) is applied only when a
source actually exposes both components — none of the currently-live
sources (SpiceJet, Akasa) show that breakdown on their search-results
view (both display one tax-inclusive total), so those rows keep
base_fare/taxes_fees as NULL rather than a fabricated split. This function
is still exercised by tests against a synthetic source that does provide
both fields, so the capability is real and ready for a source that does.

Storage is per-row resilient: each quote is flushed and committed
individually, so a single malformed row (a constraint violation, a
transient DB error) is skipped and logged rather than silently discarding
every other row collected in the same batch. This matters because
clean_and_store is the last step of a scrape cycle — before this, one bad
row could sink an entire day's worth of otherwise-good data.
"""
from __future__ import annotations

import datetime as dt
import logging
import statistics as stats
from collections import defaultdict

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import PLAUSIBLE_FARE_INR_RANGE
from app.db.models import Carrier, FareQuote, Route
from app.pipeline.dedupe import dedupe_raw_quotes
from app.scraper.base import RawQuote

logger = logging.getLogger("airfare_idex.pipeline")

OUTLIER_Z_THRESHOLD = 3.5  # standard robust-z cutoff (Iglewicz & Hoaglin, 1993)
MIN_GROUP_SIZE_FOR_OUTLIER_CHECK = 4


def is_plausible_fare(total_fare: float) -> bool:
    """A coarse sanity bound distinct from statistical outlier detection:
    this catches scraper/parsing bugs (e.g. accidentally reading a seat
    count or a date as the price) rather than genuine price variance. A
    real domestic fare well outside PLAUSIBLE_FARE_INR_RANGE almost
    certainly means a selector broke, not that someone is paying it."""
    low, high = PLAUSIBLE_FARE_INR_RANGE
    return low <= total_fare <= high


def robust_outlier_mask(values: list[float], threshold: float = OUTLIER_Z_THRESHOLD) -> list[bool]:
    """Median/MAD-based robust z-score. Returns True where a value is an
    outlier. Groups smaller than MIN_GROUP_SIZE_FOR_OUTLIER_CHECK are left
    unflagged — not enough points to judge what's "normal" yet."""
    n = len(values)
    if n < MIN_GROUP_SIZE_FOR_OUTLIER_CHECK:
        return [False] * n

    median = stats.median(values)
    abs_devs = [abs(v - median) for v in values]
    mad = stats.median(abs_devs)

    if mad == 0:
        return [False] * n

    # 0.6745 makes the MAD-based score comparable to a standard-normal z-score
    return [abs(0.6745 * (v - median) / mad) > threshold for v in values]


def decompose_fare(total_fare: float | None, base_fare: float | None, taxes_fees: float | None) -> tuple[float | None, float | None]:
    """Returns (base_fare, taxes_fees). Passes through real values when the
    source provided both; otherwise leaves both null rather than guessing."""
    if base_fare is not None and taxes_fees is not None:
        return base_fare, taxes_fees
    if base_fare is not None and total_fare is not None:
        return base_fare, round(total_fare - base_fare, 2)
    if taxes_fees is not None and total_fare is not None:
        return round(total_fare - taxes_fees, 2), taxes_fees
    return None, None


def _get_or_create_route(session: Session, origin: str, destination: str) -> Route:
    # A route is the same route regardless of which way it was searched —
    # match either direction so "DEL-BOM" and "BOM-DEL" never fragment into
    # two Route rows just because one scrape ran before a config reorder.
    route = session.execute(
        select(Route).where(
            or_(
                and_(Route.origin == origin, Route.destination == destination),
                and_(Route.origin == destination, Route.destination == origin),
            )
        )
    ).scalar_one_or_none()
    if route is None:
        from app.config import AIRPORT_NAMES

        display = f"{AIRPORT_NAMES.get(origin, origin)}-{AIRPORT_NAMES.get(destination, destination)}"
        route = Route(origin=origin, destination=destination, display_name=display)
        session.add(route)
        session.flush()
    return route


def _get_or_create_carrier(session: Session, code: str) -> Carrier:
    carrier = session.get(Carrier, code)
    if carrier is None:
        from app.config import SOURCE_REGISTRY

        name = next((s.name for s in SOURCE_REGISTRY.values() if s.carrier_code == code), code)
        carrier = Carrier(code=code, name=name)
        session.add(carrier)
        session.flush()
    return carrier


def clean_and_store(session: Session, run_id: int, raw_quotes: list[RawQuote]) -> int:
    """Cleans and stores one batch of raw quotes, returning how many rows
    were actually inserted. Each row is committed individually — if one
    row fails (a constraint violation, a transient DB error), it's logged
    and skipped, and every other row in the batch still gets stored."""
    quotes = dedupe_raw_quotes(raw_quotes)

    groups: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    for idx, q in enumerate(quotes):
        if q.total_fare is not None:
            groups[(q.origin, q.destination, q.ap_window_days)].append(idx)

    outlier_flags = [False] * len(quotes)
    for _key, idxs in groups.items():
        values = [quotes[i].total_fare for i in idxs]
        mask = robust_outlier_mask(values)
        for i, is_out in zip(idxs, mask):
            outlier_flags[i] = is_out

    inserted = 0
    skipped = 0
    now = dt.datetime.utcnow()
    for q, is_outlier in zip(quotes, outlier_flags):
        if q.total_fare is not None and not is_plausible_fare(q.total_fare):
            logger.warning(
                "implausible fare %.2f for %s-%s (ap=%d) from %s — flagging as outlier, not a real price",
                q.total_fare, q.origin, q.destination, q.ap_window_days, q.source_id,
            )
            is_outlier = True

        try:
            route = _get_or_create_route(session, q.origin, q.destination)
            carrier = _get_or_create_carrier(session, q.carrier_code)
            base_fare, taxes_fees = decompose_fare(q.total_fare, q.base_fare, q.taxes_fees)

            session.add(
                FareQuote(
                    route_id=route.id,
                    carrier_code=carrier.code,
                    source_id=q.source_id or _infer_source_id(q),
                    scrape_run_id=run_id,
                    ap_window_days=q.ap_window_days,
                    search_date=dt.datetime.combine(q.search_date, dt.time.min),
                    travel_date=dt.datetime.combine(q.travel_date, dt.time.min),
                    fare_class=q.fare_class,
                    base_fare=base_fare,
                    taxes_fees=taxes_fees,
                    total_fare=q.total_fare,
                    is_outlier=is_outlier,
                    sold_out=q.sold_out,
                    scraped_at=now,
                    raw_snapshot_path=q.raw_snapshot_path,
                )
            )
            session.commit()
            inserted += 1
        except Exception:
            session.rollback()
            skipped += 1
            logger.exception(
                "failed to store one fare quote (route=%s-%s, carrier=%s) — skipping just this row",
                q.origin, q.destination, q.carrier_code,
            )

    if skipped:
        logger.warning("clean_and_store: %d row(s) skipped out of %d", skipped, len(quotes))
    return inserted


def _infer_source_id(q: RawQuote) -> str:
    from app.config import SOURCE_REGISTRY

    for source_id, info in SOURCE_REGISTRY.items():
        if info.carrier_code == q.carrier_code:
            return source_id
    return "unknown"
