"""Data-integrity checks a maintainer can run on demand
(`python -m app.cli validate-data`) to sanity-check the live database,
rather than only discovering a problem when a number on the dashboard
looks wrong. Every check here is read-only and returns a plain structure
describing what it found — this module never modifies data.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import PLAUSIBLE_FARE_INR_RANGE, ROUTE_BASKET
from app.db.models import Carrier, FareQuote, IndexValue, Route, ScrapeRun

# A ScrapeRun stuck in "running" longer than this almost certainly means
# the process was killed (SIGKILL, machine sleep, OOM) rather than caught
# by run_scrape_cycle's own exception handling — the one failure mode the
# crash-resilience fix in app.scraper.runner cannot durably record after
# the fact, since there's no handler left alive to record it.
STUCK_RUN_THRESHOLD = dt.timedelta(hours=2)


def validate_data(session: Session) -> dict:
    checks: list[dict] = []

    # 1. Duplicate routes for the same city pair (either direction) — the
    #    UniqueConstraint + _get_or_create_route's match-either-direction
    #    logic should prevent new ones, but old data (pre-fix) or a future
    #    regression could still produce them.
    routes = session.execute(select(Route)).scalars().all()
    seen_pairs: dict[frozenset, list[str]] = {}
    for r in routes:
        key = frozenset([r.origin, r.destination])
        seen_pairs.setdefault(key, []).append(r.display_name)
    dup_routes = {"-".join(sorted(names)): names for names in seen_pairs.values() if len(names) > 1}
    checks.append(
        {
            "check": "duplicate_routes",
            "ok": len(dup_routes) == 0,
            "detail": f"{len(dup_routes)} city pair(s) with more than one Route row" if dup_routes else "none found",
            "examples": list(dup_routes.values())[:5],
        }
    )

    # 2. Routes carrying real fare data that have fallen out of the
    #    current ROUTE_BASKET (stale after a basket re-rank) — not
    #    necessarily wrong, but worth surfacing.
    basket_pairs = {frozenset(p) for p in ROUTE_BASKET}
    off_basket = [r.display_name for r in routes if frozenset([r.origin, r.destination]) not in basket_pairs]
    checks.append(
        {
            "check": "routes_outside_current_basket",
            "ok": len(off_basket) == 0,
            "detail": f"{len(off_basket)} route(s) with data are no longer in ROUTE_BASKET" if off_basket else "none found",
            "examples": off_basket[:5],
        }
    )

    # 3. Fares stored outside the plausible range without is_outlier set —
    #    should be impossible given clean.py flags these at insert time;
    #    a hit here means either older data predates that check, or the
    #    check was bypassed some other way (e.g. a direct DB edit).
    low, high = PLAUSIBLE_FARE_INR_RANGE
    unflagged_implausible = session.execute(
        select(func.count(FareQuote.id)).where(
            FareQuote.total_fare.is_not(None),
            FareQuote.is_outlier.is_(False),
            (FareQuote.total_fare < low) | (FareQuote.total_fare > high),
        )
    ).scalar_one()
    checks.append(
        {
            "check": "implausible_fares_not_flagged",
            "ok": unflagged_implausible == 0,
            "detail": (
                f"{unflagged_implausible} fare(s) outside INR {low:.0f}-{high:.0f} are NOT flagged as outliers"
                if unflagged_implausible
                else "none found"
            ),
        }
    )

    # 4. Orphaned FareQuote rows (FK should now prevent new ones — see
    #    app.db.session's foreign_keys=ON pragma — but this catches
    #    anything from before that was enabled).
    orphaned_route = session.execute(
        select(func.count(FareQuote.id)).where(FareQuote.route_id.not_in(select(Route.id)))
    ).scalar_one()
    orphaned_carrier = session.execute(
        select(func.count(FareQuote.id)).where(FareQuote.carrier_code.not_in(select(Carrier.code)))
    ).scalar_one()
    checks.append(
        {
            "check": "orphaned_fare_quotes",
            "ok": orphaned_route == 0 and orphaned_carrier == 0,
            "detail": f"{orphaned_route} with a missing route, {orphaned_carrier} with a missing carrier",
        }
    )

    # 5. ScrapeRun rows stuck in "running" — see STUCK_RUN_THRESHOLD.
    cutoff = dt.datetime.utcnow() - STUCK_RUN_THRESHOLD
    stuck_runs = session.execute(
        select(ScrapeRun.id, ScrapeRun.started_at).where(ScrapeRun.status == "running", ScrapeRun.started_at < cutoff)
    ).all()
    checks.append(
        {
            "check": "stuck_running_scrape_runs",
            "ok": len(stuck_runs) == 0,
            "detail": (
                f"{len(stuck_runs)} run(s) still 'running' after {STUCK_RUN_THRESHOLD}: "
                f"ids {[r.id for r in stuck_runs]}"
                if stuck_runs
                else "none found"
            ),
        }
    )

    # 6. Failed scrape runs, surfaced (not an "error" state itself — a
    #    failure that WAS recorded is the fix working as intended — but a
    #    maintainer should still see it).
    failed_runs = session.execute(
        select(func.count(ScrapeRun.id)).where(ScrapeRun.status == "error")
    ).scalar_one()
    checks.append(
        {
            "check": "recorded_failed_runs",
            "ok": True,  # informational, not a failure of this check
            "detail": f"{failed_runs} run(s) recorded status=error (informational — see their .notes for why)",
        }
    )

    # 7. Non-finite or non-positive IndexValue rows.
    bad_index_values = session.execute(
        select(func.count(IndexValue.id)).where(IndexValue.value <= 0)
    ).scalar_one()
    checks.append(
        {
            "check": "non_positive_index_values",
            "ok": bad_index_values == 0,
            "detail": f"{bad_index_values} index_values row(s) with value <= 0" if bad_index_values else "none found",
        }
    )

    return {
        "checks": checks,
        "all_ok": all(c["ok"] for c in checks),
    }
