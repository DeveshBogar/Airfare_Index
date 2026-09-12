"""Per-carrier Airfare Price Index: the identical Laspeyres/Paasche/Fisher
construction app.index.construct uses for the headline index, scoped to
one carrier's own fares, plus each carrier's weighted contribution to that
headline index.

Per-carrier index construction
-------------------------------
No separate math lives here for the index itself — construct.
compute_index_series(session, carrier_code=...) *is* the same function
the headline index uses, just with FareQuote rows pre-filtered to one
carrier before the exact same base-day/weighting/Laspeyres-Paasche-Fisher
logic runs. A carrier's series therefore tracks only how *that carrier's*
own cheapest fares moved, not the whole-market cheapest-of-all-carriers
figure the headline index reports.

Carrier weight ("market share on the tracked routes")
-------------------------------------------------------
Read literally, "derive this from the same DGCA traffic data already used
for route weights" is not fully answerable: the DGCA city-pair CSV this
project has (data/reference/dgca_city_pair_traffic.csv) reports only City1/
City2/PaxToCity2/PaxFromCity2 — city-pair passenger totals, with no
per-carrier breakdown at all. DGCA does separately publish an airline-wise
market-share report, but that file is not part of this project's data,
and using an unverified number pulled from memory would be exactly the
kind of fabricated figure this project refuses elsewhere (see weights.py's
own docstring on the same tension for Paasche weights).

So the weight below is the same real DGCA route-weight data genuinely
combined with something this project does actually observe: which
carrier(s) our own scrapers found quoting a real, non-outlier price on
each route. Concretely, for carrier c:

    carrier_weight(c) = Σ_r  w_r  x  quotes(c, r) / quotes(*, r)

where `w_r` is route r's real DGCA-derived weight (app.index.weights.
compute_route_weights, computed over exactly the set of routes with any
real carrier data — so Σ_r w_r = 1 over that set) and quotes(c, r) is a
count of this project's own real, non-outlier, non-sold-out fare_quotes
rows for carrier c on route r. Summed over all carriers on a route, the
quote-share term is 1, so Σ_c carrier_weight(c) = 1 across carriers with
any data — carrier_weight is a proper partition of the headline index,
not an independent number that happens to look like one.

This is a real, DGCA-route-weighted share of THIS PROJECT'S OWN OBSERVED
QUOTING ACTIVITY — a meaningfully smaller and different claim than
official DGCA/airline passenger market share, and the API/dashboard must
say so rather than imply the latter. With only SpiceJet and Akasa
currently live (see docs/ethics_compliance.md), this mostly reflects
which of the two happened to have a cheaper/quotable fare on a given
route on a given day, not fleet size or true traffic share.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CarrierIndexValue, FareQuote, Route
from app.index.construct import compute_index_series
from app.index.weights import compute_route_weights


def active_carriers(session: Session) -> list[str]:
    """Carrier codes with at least one real (non-outlier, non-sold-out,
    priced) fare quote anywhere in the database, sorted for a stable,
    reproducible iteration order."""
    rows = session.execute(
        select(FareQuote.carrier_code)
        .distinct()
        .where(
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()
    return sorted(r[0] for r in rows)


def compute_carrier_weights(session: Session) -> dict[str, float]:
    """{carrier_code: weight}, normalized so weights sum to 1 across every
    carrier with any real fare data — see this module's docstring for
    exactly what the weight does and does not represent. Empty dict if
    there's no real fare data yet."""
    rows = session.execute(
        select(FareQuote.carrier_code, Route.origin, Route.destination)
        .join(Route, FareQuote.route_id == Route.id)
        .where(
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()
    if not rows:
        return {}

    counts_by_route: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for carrier_code, origin, destination in rows:
        counts_by_route[(origin, destination)][carrier_code] += 1

    route_weight_info = compute_route_weights(list(counts_by_route.keys()))
    route_weights = {pair: info["weight"] for pair, info in route_weight_info.items()}

    carrier_totals: dict[str, float] = defaultdict(float)
    for pair, carrier_counts in counts_by_route.items():
        w_route = route_weights.get(pair, 0.0)
        route_total = sum(carrier_counts.values())
        for carrier_code, n in carrier_counts.items():
            carrier_totals[carrier_code] += w_route * (n / route_total)

    # Σ_r w_r = 1 over this exact route set and Σ_c quote_share(c, r) = 1
    # per route, so grand_total is already ~1 — this guards only against
    # float drift, not a real second source of imbalance.
    grand_total = sum(carrier_totals.values()) or 1.0
    return {carrier: total / grand_total for carrier, total in carrier_totals.items()}


def compute_all_carrier_index_series(session: Session) -> dict[str, list[dict]]:
    """{carrier_code: [per-day index dicts]} for every carrier with real
    fare data, each series carrying its own `carrier_weight` (constant
    across that carrier's whole series — it's a current snapshot of
    observed-quoting share, not itself a time series)."""
    weights = compute_carrier_weights(session)
    result: dict[str, list[dict]] = {}
    for carrier_code in active_carriers(session):
        series = compute_index_series(session, carrier_code=carrier_code)
        weight = weights.get(carrier_code, 0.0)
        for row in series:
            row["carrier_weight"] = weight
        result[carrier_code] = series
    return result


def persist_carrier_index_values(
    session: Session, by_carrier: dict[str, list[dict]], frequency: str = "daily"
) -> int:
    now = dt.datetime.utcnow()
    written = 0
    for carrier_code, series in by_carrier.items():
        for row in series:
            for method in ("laspeyres", "paasche", "fisher"):
                existing = session.execute(
                    select(CarrierIndexValue).where(
                        CarrierIndexValue.carrier_code == carrier_code,
                        CarrierIndexValue.date == dt.datetime.combine(row["date"], dt.time.min),
                        CarrierIndexValue.frequency == frequency,
                        CarrierIndexValue.method == method,
                    )
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        CarrierIndexValue(
                            carrier_code=carrier_code,
                            date=dt.datetime.combine(row["date"], dt.time.min),
                            frequency=frequency,
                            method=method,
                            value=row[method],
                            carrier_weight=row["carrier_weight"],
                            sample_size=row["sample_size"],
                            routes_covered=row["routes_covered"],
                            computed_at=now,
                        )
                    )
                else:
                    existing.value = row[method]
                    existing.carrier_weight = row["carrier_weight"]
                    existing.sample_size = row["sample_size"]
                    existing.routes_covered = row["routes_covered"]
                    existing.computed_at = now
                written += 1
    session.flush()
    return written


def run_carrier_index_construction(session: Session) -> dict[str, list[dict]]:
    by_carrier = compute_all_carrier_index_series(session)
    persist_carrier_index_values(session, by_carrier)
    return by_carrier
