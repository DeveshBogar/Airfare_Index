"""Command-line entry points for manual operation:

    python -m app.cli seed-dgca-weights     # (re)compute + persist route weights from the DGCA CSV
    python -m app.cli run-once              # one scrape cycle across every registered source
    python -m app.cli build-index           # (re)compute the index from whatever fare data exists
    python -m app.cli detect-anomalies      # flag statistically elevated real fares (--backfill for all history)
    python -m app.cli backtest              # print the current back-test report
    python -m app.cli rank-routes           # print the top-N routes by real DGCA traffic
    python -m app.cli merge-duplicate-routes  # one-time cleanup for direction-fragmented routes
    python -m app.cli validate-data         # sanity-check the live database, exits non-zero on failure

This is also what the registered scheduled task runs daily (run-once then
build-index) — see docs/architecture.md for why that external trigger is
the single source of truth for collection rather than an in-process timer.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json

from sqlalchemy import select

from app.backtest.run_backtest import backtest_report
from app.config import DGCA_TRAFFIC_CSV, ROUTE_BASKET
from app.data_quality import validate_data
from app.db.models import FareQuote, Route, RouteWeight
from app.db.session import get_session, init_db
from app.index.anomaly_detection import detect_all_anomalies, persist_anomaly_flags, run_anomaly_detection
from app.index.carrier_index import run_carrier_index_construction
from app.index.construct import run_index_construction
from app.index.weights import compute_route_weights, top_traffic_routes
from app.lockfile import ScrapeAlreadyRunning, scrape_lock
from app.logging_config import configure_logging
from app.pipeline.clean import _get_or_create_route
from app.scraper.runner import run_scrape_cycle

configure_logging()


def seed_dgca_weights() -> None:
    init_db()
    with get_session() as session:
        weights = compute_route_weights()
        as_of = dt.date.today().strftime("%Y-%m")
        for (origin, destination), info in weights.items():
            route = _get_or_create_route(session, origin, destination)
            existing = (
                session.query(RouteWeight)
                .filter_by(route_id=route.id, as_of=as_of)
                .one_or_none()
            )
            if existing is None:
                session.add(
                    RouteWeight(
                        route_id=route.id,
                        as_of=as_of,
                        passengers=info["passengers"],
                        weight=info["weight"],
                        source_file=str(DGCA_TRAFFIC_CSV),
                    )
                )
            else:
                existing.passengers = info["passengers"]
                existing.weight = info["weight"]
            print(f"{origin}-{destination}: passengers={info['passengers']:.0f} weight={info['weight']:.4f}")


def run_once(source_ids: list[str] | None = None) -> None:
    init_db()
    try:
        with scrape_lock():
            with get_session() as session:
                run = asyncio.run(run_scrape_cycle(session, source_ids=source_ids))
                print(f"run {run.id}: status={run.status} quotes={run.quotes_collected}")
                print(run.notes)
    except ScrapeAlreadyRunning as exc:
        print(f"refusing to start: {exc}")
        raise SystemExit(1) from exc


def build_index() -> None:
    init_db()
    with get_session() as session:
        series = run_index_construction(session)
        print(f"computed {len(series)} day(s) of index values")
        for row in series:
            print(
                f"  {row['date']}  laspeyres={row['laspeyres']:.2f}  "
                f"paasche={row['paasche']:.2f}  fisher={row['fisher']:.2f}  "
                f"(n={row['sample_size']}, routes={row['routes_covered']})"
            )

        by_carrier = run_carrier_index_construction(session)
        for carrier_code, carrier_series in by_carrier.items():
            weight = carrier_series[-1]["carrier_weight"] if carrier_series else 0.0
            print(f"computed {len(carrier_series)} day(s) of {carrier_code} index values (weight={weight:.3f})")

        # Runs on the same single daily trigger as the index itself rather
        # than a second scheduler — see docs/architecture.md on why this
        # project keeps exactly one source of truth for scheduled work.
        flagged = run_anomaly_detection(session)
        print(f"anomaly detection: {flagged} new flag(s)")


def detect_anomalies(backfill: bool = False) -> None:
    """Flags real fares that are statistically elevated against their own
    route+carrier+booking-window history (see app.index.anomaly_detection).

    Normal mode tests only each group's most recent real day — the daily
    question, "is today unusual?". `--backfill` walks every historical day
    instead, so history collected before this feature existed still gets
    assessed rather than silently skipped. Both are idempotent: a group-day
    that already has a flag is never duplicated, and an existing flag's
    review status is never overwritten."""
    init_db()
    with get_session() as session:
        if not backfill:
            written = run_anomaly_detection(session)
            print(f"anomaly detection: {written} new flag(s)")
            return

        days = sorted(
            {
                (d.date() if hasattr(d, "date") else d)
                for (d,) in session.execute(select(FareQuote.search_date)).all()
            }
        )
        total = 0
        for day in days:
            total += persist_anomaly_flags(session, detect_all_anomalies(session, as_of=day))
        print(f"anomaly detection (backfill over {len(days)} real day(s)): {total} new flag(s)")


def rank_routes(n: int = 25) -> None:
    """Prints the current top-N India routes by real DGCA traffic —
    regenerate app.config.ROUTE_BASKET from this after refreshing the CSV."""
    from app.config import AIRPORT_NAMES

    for (o, d), pax in top_traffic_routes(n=n):
        print(f'    ("{o}", "{d}"),   # {pax:,.0f} pax  ({AIRPORT_NAMES.get(o, o)}-{AIRPORT_NAMES.get(d, d)})')


def merge_duplicate_routes() -> None:
    """One-time cleanup for Route rows that fragmented by direction (e.g.
    "DEL-BOM" and "BOM-DEL" as two separate rows) before
    app.pipeline.clean._get_or_create_route started matching either
    direction. Reassigns fare_quotes/route_weights to one canonical row
    per city pair (preferring whichever direction config.ROUTE_BASKET
    declares) and deletes the duplicate."""
    init_db()
    basket_pairs = {frozenset(p) for p in ROUTE_BASKET}
    with get_session() as session:
        routes = session.query(Route).all()
        canonical_by_pair: dict[frozenset, Route] = {}
        merged = 0
        for route in routes:
            key = frozenset([route.origin, route.destination])
            existing = canonical_by_pair.get(key)
            if existing is None:
                canonical_by_pair[key] = route
                continue

            # Prefer whichever of the two rows matches ROUTE_BASKET's
            # declared (origin, destination) order; otherwise keep the
            # lower id (first created).
            route_matches_basket = (route.origin, route.destination) in ROUTE_BASKET
            existing_matches_basket = (existing.origin, existing.destination) in ROUTE_BASKET
            if route_matches_basket and not existing_matches_basket:
                keep, drop = route, existing
            elif existing_matches_basket and not route_matches_basket:
                keep, drop = existing, route
            elif existing.id < route.id:
                keep, drop = existing, route
            else:
                keep, drop = route, existing
            session.query(FareQuote).filter(FareQuote.route_id == drop.id).update({"route_id": keep.id})
            # RouteWeight has a unique (route_id, as_of) constraint and
            # `keep` already has (or will get, from a re-seed) its own
            # weight for each period — computed from real DGCA data that
            # matches either direction — so drop's rows are redundant
            # duplicates, not data to preserve. Delete rather than
            # reassign to avoid colliding with keep's own row.
            session.query(RouteWeight).filter(RouteWeight.route_id == drop.id).delete()
            session.delete(drop)
            canonical_by_pair[key] = keep
            merged += 1
            print(f"merged {drop.display_name} ({drop.origin}-{drop.destination}) into {keep.display_name}")

        session.flush()
        print(f"done: merged {merged} duplicate route(s), {len(canonical_by_pair)} route(s) remain")


def backtest() -> None:
    init_db()
    with get_session() as session:
        report = backtest_report(session)
        print(json.dumps(report, indent=2))


def validate_data_cmd() -> None:
    """Sanity-checks the live database and prints a pass/fail report per
    check — run this after a scrape or on a schedule to catch data
    problems before they show up as a wrong number on the dashboard."""
    init_db()
    with get_session() as session:
        result = validate_data(session)
        for check in result["checks"]:
            status = "OK  " if check["ok"] else "FAIL"
            print(f"[{status}] {check['check']}: {check['detail']}")
            for example in check.get("examples", []):
                print(f"         - {example}")
        print()
        print("All checks passed." if result["all_ok"] else "Some checks failed — see FAIL lines above.")
    if not result["all_ok"]:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="airfare-idex")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed-dgca-weights")
    p_run = sub.add_parser("run-once")
    p_run.add_argument("--sources", nargs="*", default=None)
    sub.add_parser("build-index")
    p_anomalies = sub.add_parser("detect-anomalies")
    p_anomalies.add_argument("--backfill", action="store_true", default=False)
    sub.add_parser("backtest")
    p_rank = sub.add_parser("rank-routes")
    p_rank.add_argument("--n", type=int, default=25)
    sub.add_parser("merge-duplicate-routes")
    sub.add_parser("validate-data")

    args = parser.parse_args()
    if args.command == "seed-dgca-weights":
        seed_dgca_weights()
    elif args.command == "run-once":
        run_once(args.sources)
    elif args.command == "build-index":
        build_index()
    elif args.command == "detect-anomalies":
        detect_anomalies(backfill=args.backfill)
    elif args.command == "backtest":
        backtest()
    elif args.command == "rank-routes":
        rank_routes(args.n)
    elif args.command == "merge-duplicate-routes":
        merge_duplicate_routes()
    elif args.command == "validate-data":
        validate_data_cmd()


if __name__ == "__main__":
    main()
