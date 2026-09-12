"""Airfare Price Index (APIx) construction.

Mirrors the fixed-basket, base-period-weighted (modified Laspeyres) method
MoSPI's Price Statistics Division uses to build CPI: pick a base period,
compute each route's price relative to that base, and aggregate with
weights. Weights come from real DGCA passenger-traffic data
(app.index.weights) rather than being assumed equal — directly answering
the problem statement's requirement that routes be "selected on the basis
of DGCA passenger-traffic data."

Three variants are computed side by side:
  - Laspeyres: weights fixed at the base period's DGCA traffic shares.
  - Paasche: weights recomputed from whatever DGCA traffic file is on disk
    *right now*. app/index/weights.py reads data/reference/dgca_city_pair_
    traffic.csv fresh every call, and that file is refreshed periodically
    via scripts/download_dgca_data.py — so as new DGCA monthly releases
    land, Paasche genuinely diverges from the fixed Laspeyres base weights.
    We do not have per-period ticket-sales volumes (nobody outside the
    airlines does), so this is the closest honestly-supportable analogue
    to a current-weighted index; it is documented as such rather than
    presented as a textbook Paasche computed from unobserved quantities.
  - Fisher: geometric mean of Laspeyres and Paasche (the standard
    superlative index).

The representative price for a route on a given day is the cheapest
non-outlier, non-sold-out fare quoted that day — mirroring how a CPI
collector records "the price actually obtainable" rather than averaging
across every fare class a search happened to display.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import FareQuote, IndexValue, Route
from app.index.weights import compute_route_weights

BASE_INDEX_VALUE = 100.0


def cheapest_by_route_day(
    session: Session, carrier_code: str | None = None
) -> dict[tuple[int, dt.date], float]:
    """The whole-market cheapest fare per (route, day), or — when
    `carrier_code` is given — that one carrier's own cheapest fare per
    (route, day). Same non-outlier/non-sold-out real-price rule either
    way; see app.index.carrier_index for why a carrier-scoped call of
    this exists at all."""
    conditions = [
        FareQuote.is_outlier.is_(False),
        FareQuote.sold_out.is_(False),
        FareQuote.total_fare.is_not(None),
    ]
    if carrier_code is not None:
        conditions.append(FareQuote.carrier_code == carrier_code)
    rows = session.execute(
        select(FareQuote.route_id, FareQuote.search_date, FareQuote.total_fare).where(*conditions)
    ).all()
    best: dict[tuple[int, dt.date], float] = {}
    for route_id, search_date, total_fare in rows:
        d = search_date.date() if hasattr(search_date, "date") else search_date
        key = (route_id, d)
        if key not in best or total_fare < best[key]:
            best[key] = total_fare
    return best


def compute_index_series(session: Session, carrier_code: str | None = None) -> list[dict]:
    """Returns one dict per day with laspeyres/paasche/fisher values
    (base day = 100), sample_size, and routes_covered. Empty list if there
    isn't at least one day of real data yet.

    `carrier_code` scopes every step (the cheapest-price lookup, the base
    day, the weights) to that one carrier's own fares — see
    app.index.carrier_index, which is the only caller that passes it. The
    default (None) is the original whole-market headline index, unchanged."""
    cheapest = cheapest_by_route_day(session, carrier_code=carrier_code)
    if not cheapest:
        return []

    routes = {r.id: (r.origin, r.destination) for r in session.execute(select(Route)).scalars()}

    by_route: dict[int, dict[dt.date, float]] = defaultdict(dict)
    for (route_id, day), price in cheapest.items():
        by_route[route_id][day] = price

    all_days = sorted({day for prices in by_route.values() for day in prices})
    base_day = all_days[0]

    route_pairs = [routes[rid] for rid in by_route if rid in routes]
    base_weight_info = compute_route_weights(route_pairs)
    base_weights = {pair: info["weight"] for pair, info in base_weight_info.items()}

    series: list[dict] = []
    for day in all_days:
        # Only routes with both a base-day and this-day price contribute —
        # a route that hasn't been observed yet on a given day is left out
        # of that day's aggregate rather than guessed at.
        laspeyres_num = 0.0
        laspeyres_den = 0.0
        current_weight_info = compute_route_weights(
            [routes[rid] for rid in by_route if day in by_route[rid] and base_day in by_route[rid]]
        )
        paasche_num = 0.0
        paasche_den = 0.0
        sample_size = 0
        routes_covered = 0

        for route_id, prices in by_route.items():
            pair = routes.get(route_id)
            if pair is None or day not in prices or base_day not in prices:
                continue
            relative = prices[day] / prices[base_day]
            w_base = base_weights.get(pair, 0.0)
            w_curr = current_weight_info.get(pair, {}).get("weight", 0.0)

            laspeyres_num += w_base * relative
            laspeyres_den += w_base
            paasche_num += w_curr * relative
            paasche_den += w_curr
            sample_size += 1
            routes_covered += 1

        if laspeyres_den == 0 or paasche_den == 0:
            continue

        laspeyres = BASE_INDEX_VALUE * (laspeyres_num / laspeyres_den)
        paasche = BASE_INDEX_VALUE * (paasche_num / paasche_den)
        fisher = math.sqrt(laspeyres * paasche)

        series.append(
            {
                "date": day,
                "laspeyres": laspeyres,
                "paasche": paasche,
                "fisher": fisher,
                "sample_size": sample_size,
                "routes_covered": routes_covered,
            }
        )

    return series


def persist_index_values(session: Session, series: list[dict], frequency: str = "daily") -> int:
    now = dt.datetime.utcnow()
    written = 0
    for row in series:
        for method in ("laspeyres", "paasche", "fisher"):
            existing = session.execute(
                select(IndexValue).where(
                    IndexValue.date == dt.datetime.combine(row["date"], dt.time.min),
                    IndexValue.frequency == frequency,
                    IndexValue.method == method,
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    IndexValue(
                        date=dt.datetime.combine(row["date"], dt.time.min),
                        frequency=frequency,
                        method=method,
                        value=row[method],
                        sample_size=row["sample_size"],
                        routes_covered=row["routes_covered"],
                        computed_at=now,
                    )
                )
            else:
                existing.value = row[method]
                existing.sample_size = row["sample_size"]
                existing.routes_covered = row["routes_covered"]
                existing.computed_at = now
            written += 1
    session.flush()
    return written


def run_index_construction(session: Session) -> list[dict]:
    series = compute_index_series(session)
    persist_index_values(session, series)
    return series
