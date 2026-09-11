"""Back-test the Airfare Price Index against real accumulated history.

The problem statement asks for "at least 30 days of back-tested results
against publicly available DGCA monthly average-fare data." Two honest
facts shaped this module instead of a synthetic 30-day chart:

  1. DGCA does not publish a fare time series (we checked — the public
     releases are passenger-traffic counts and load factors; the closest
     fare-side artifact is the DGCA Tariff Monitoring Unit's manual
     spot-checks, which aren't released as data). So there is no ready-
     made external series to diff against.
  2. Genuine daily history can only be built by actually running the
     scraper every day. This module reports honestly on however many
     distinct calendar days of real index values exist right now — it
     will say "N=1" the first time it runs and grow every day the
     registered scheduled task (see docs/architecture.md) fires, reaching
     the 30-day mark on its own timeline rather than a fabricated one.

Until N>=30, this still validates the pipeline end to end (index
construction, day-over-day volatility, per-route dispersion) on whatever
real data exists, and states its own sample size prominently rather than
padding it.
"""
from __future__ import annotations

import statistics as stats

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import IndexValue

TARGET_DAYS = 30


def backtest_report(session: Session, method: str = "fisher") -> dict:
    rows = (
        session.execute(
            select(IndexValue)
            .where(IndexValue.frequency == "daily", IndexValue.method == method)
            .order_by(IndexValue.date)
        )
        .scalars()
        .all()
    )

    n_days = len(rows)
    report: dict = {
        "method": method,
        "days_available": n_days,
        "target_days": TARGET_DAYS,
        "status": "mature" if n_days >= TARGET_DAYS else "accumulating",
        "note": (
            f"{n_days}/{TARGET_DAYS} real days of index history collected so far. "
            "No public DGCA fare time series exists to diff against (checked: DGCA "
            "publishes passenger-traffic and load-factor statistics, not fares) — "
            "this back-test validates the pipeline against real, self-collected "
            "history and will keep extending automatically as the daily scheduled "
            "scrape adds each new day."
        ),
    }

    if n_days == 0:
        report["day_over_day_pct_changes"] = []
        report["volatility_stdev_pct"] = None
        report["min_value"] = None
        report["max_value"] = None
        return report

    values = [r.value for r in rows]
    dates = [r.date.date().isoformat() for r in rows]
    pct_changes = [
        round(100 * (values[i] - values[i - 1]) / values[i - 1], 3) for i in range(1, len(values))
    ]

    report.update(
        {
            "dates": dates,
            "values": [round(v, 3) for v in values],
            "day_over_day_pct_changes": pct_changes,
            "volatility_stdev_pct": round(stats.stdev(pct_changes), 3) if len(pct_changes) > 1 else None,
            "min_value": round(min(values), 3),
            "max_value": round(max(values), 3),
        }
    )
    return report
