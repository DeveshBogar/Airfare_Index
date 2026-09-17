"""Fare-anomaly detection: flags a real, collected fare that is
statistically elevated against that same route+carrier+booking-window's own
real history, and attaches the real, dated context a human would need to
judge why.

The statistical test is not a new one. app.pipeline.clean.robust_outlier_mask
already flags outliers with a median/MAD robust z-score
(`0.6745 * (v - median) / mad`, cutoff 3.5 — the Iglewicz & Hoaglin 1993
convention), applied *within a single scrape run, across carriers*, to keep
freak values out of the index. This module applies the identical formula and
the identical constants along a different axis — *across days of history*
for one fixed (route, carrier, advance-purchase window) — with two
deliberate differences:

  - **Directional.** clean.py takes `abs()` of the z-score because a
    parsing bug can produce a wildly low number just as easily as a high
    one. Here, a fare *below* its own history is a bargain, not something a
    fare regulator needs to see, so only the positive side is ever flagged.
  - **Today only.** Only the most recent real day in each group is tested,
    against every earlier real day in that same group. A daily run
    therefore asks exactly one question — "is today's new observation
    unusual for its own history?" — and never retroactively re-flags days
    that were already assessed.

A flag additionally has to clear a materiality floor
(MIN_PCT_ABOVE_BASELINE_FOR_FLAG), because the z-score alone is necessary
but not sufficient: on a route whose fares barely move, the MAD is tiny and
a trivial increase scores an enormous z. Both tests must pass — see that
constant for the real example from this project's own data that motivated
it.

Representative price per day is the cheapest real (non-outlier,
non-sold-out, priced) fare for that group on that day — the same rule
docs/methodology.md sets out for the index itself and the same per-day
aggregation app.index.price_history already performs one dimension broader.

**Known limitation, stated rather than hidden**: median/MAD is robust to a
*minority* of elevated days by design. That same property means a
*sustained* elevated-fare period gradually gets absorbed into the baseline
and stops producing new flags. This detector is for catching departures
from a route's own recent norm, not for measuring a slow structural climb —
the index trend, CPI-divergence and spike-watch views already cover that
ground. See docs/regulator_flagging_methodology.md.

**What this module does not do**: it computes no judgement about whether a
fare is fair, lawful, justified or excessive. It reports a real number, the
real baseline it departed from, and real dated factors that a human
regulator can weigh themselves. That boundary is enforced by a regression
test (backend/tests/test_regulator_boundaries.py), not just by convention.
"""
from __future__ import annotations

import datetime as dt
import statistics as stats
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import spike_window_for_date
from app.db.models import FareQuote, RegulatorFareFlag
from app.index.financial_context import financial_context_for_carrier
from app.news.fetch_news import get_airfare_news
from app.pipeline.clean import MIN_GROUP_SIZE_FOR_OUTLIER_CHECK, OUTLIER_Z_THRESHOLD
from app.scraper.compliance import ComplianceGate

# Reused deliberately rather than re-tuned: this is the same statistical
# test as app.pipeline.clean's outlier check, so it uses the same cutoff and
# the same minimum-sample guard. A different number here would mean two
# parts of the same codebase disagreeing about what "unusual" means.
ANOMALY_Z_THRESHOLD = OUTLIER_Z_THRESHOLD
MIN_HISTORY_DAYS_FOR_ANOMALY_CHECK = MIN_GROUP_SIZE_FOR_OUTLIER_CHECK

# A flag must clear BOTH the statistical test above and this materiality
# floor. The z-score alone is necessary but not sufficient: on a very
# stable route the MAD is tiny, so a trivial move scores an enormous z.
# Real example from this project's own collected data — Delhi-Srinagar
# (SpiceJet, T+7) scored z=22.9 on a fare just 8.0% above its baseline,
# because that route's fares barely move at all. Statistically unusual for
# that route: yes. Worth a regulator's limited attention: no. A queue full
# of 8% flags teaches its user to ignore the queue, which is worse than no
# queue. 15% is set well below the genuinely serious cases this same data
# also surfaced (Mumbai-Delhi at +200%, Kolkata-Delhi at +82%) so real
# problems still come through early, while routine variance does not.
MIN_PCT_ABOVE_BASELINE_FOR_FLAG = 15.0

# How far back a news item can be published and still be offered as
# possible context for a flag. A week covers the lag between a cost/
# disruption event being reported and fares moving, without dragging in
# month-old stories that would just be noise.
NEWS_LOOKBACK_DAYS = 7

# Converts a MAD-based deviation into something comparable to a
# standard-normal z-score (same constant, same reason, as clean.py).
_MAD_TO_Z = 0.6745


@dataclass(frozen=True)
class AnomalyCandidate:
    route_id: int
    carrier_code: str
    ap_window_days: int
    flagged_search_date: dt.date
    flagged_travel_date: dt.date
    fare_quote_id: int | None
    observed_fare: float
    baseline_median_fare: float
    baseline_mad: float
    robust_z_score: float
    pct_above_baseline_median: float
    baseline_sample_size: int


def _cheapest_real_fare_per_day(
    session: Session, route_id: int, carrier_code: str, ap_window_days: int
) -> dict[dt.date, tuple[float, int]]:
    """{search_date: (cheapest_fare, fare_quote_id)} across real, priced,
    non-outlier, non-sold-out rows for this exact group."""
    rows = session.execute(
        select(FareQuote.id, FareQuote.search_date, FareQuote.total_fare).where(
            FareQuote.route_id == route_id,
            FareQuote.carrier_code == carrier_code,
            FareQuote.ap_window_days == ap_window_days,
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()

    best: dict[dt.date, tuple[float, int]] = {}
    for quote_id, search_date, total_fare in rows:
        day = search_date.date() if hasattr(search_date, "date") else search_date
        current = best.get(day)
        if current is None or total_fare < current[0]:
            best[day] = (total_fare, quote_id)
    return best


def detect_anomaly_for_group(
    session: Session,
    route_id: int,
    carrier_code: str,
    ap_window_days: int,
    as_of: dt.date | None = None,
) -> AnomalyCandidate | None:
    """Tests the most recent real day in this group (or the most recent day
    up to and including `as_of`, for backfill) against every earlier real
    day in the same group. Returns None when there isn't enough history,
    when the baseline has no spread to measure against, or when the fare
    simply isn't elevated."""
    by_day = _cheapest_real_fare_per_day(session, route_id, carrier_code, ap_window_days)
    if not by_day:
        return None

    candidate_days = sorted(d for d in by_day if as_of is None or d <= as_of)
    if len(candidate_days) < MIN_HISTORY_DAYS_FOR_ANOMALY_CHECK + 1:
        # Need the tested day PLUS enough prior days to know what normal is.
        return None

    tested_day = candidate_days[-1]
    baseline_days = candidate_days[:-1]
    baseline_values = [by_day[d][0] for d in baseline_days]

    median = stats.median(baseline_values)
    mad = stats.median([abs(v - median) for v in baseline_values])
    if mad == 0:
        # A perfectly flat baseline gives no scale to judge a departure
        # against — same call clean.py makes for the same reason.
        return None

    observed, quote_id = by_day[tested_day]
    z = _MAD_TO_Z * (observed - median) / mad
    if z <= ANOMALY_Z_THRESHOLD:
        return None

    pct_above = 100.0 * (observed - median) / median
    if pct_above < MIN_PCT_ABOVE_BASELINE_FOR_FLAG:
        # Statistically unusual but not materially elevated — see
        # MIN_PCT_ABOVE_BASELINE_FOR_FLAG on why both tests must pass.
        return None

    return AnomalyCandidate(
        route_id=route_id,
        carrier_code=carrier_code,
        ap_window_days=ap_window_days,
        flagged_search_date=tested_day,
        flagged_travel_date=tested_day + dt.timedelta(days=ap_window_days),
        fare_quote_id=quote_id,
        observed_fare=round(observed, 2),
        baseline_median_fare=round(median, 2),
        baseline_mad=round(mad, 2),
        robust_z_score=round(z, 3),
        pct_above_baseline_median=round(pct_above, 2),
        baseline_sample_size=len(baseline_values),
    )


def detect_all_anomalies(session: Session, as_of: dt.date | None = None) -> list[AnomalyCandidate]:
    """Runs the test over every (route, carrier, AP-window) group that has
    any real fare data at all."""
    groups = session.execute(
        select(FareQuote.route_id, FareQuote.carrier_code, FareQuote.ap_window_days)
        .distinct()
        .where(
            FareQuote.is_outlier.is_(False),
            FareQuote.sold_out.is_(False),
            FareQuote.total_fare.is_not(None),
        )
    ).all()

    candidates = []
    for route_id, carrier_code, ap_window_days in groups:
        found = detect_anomaly_for_group(session, route_id, carrier_code, ap_window_days, as_of=as_of)
        if found is not None:
            candidates.append(found)
    return candidates


def why_context_for_flag(
    session: Session,
    carrier_code: str,
    flagged_travel_date: dt.date,
    flagged_search_date: dt.date,
    gate: ComplianceGate | None = None,
) -> list[dict]:
    """Real, dated factors that *may* bear on an elevated fare, each drawn
    from a source this project already collects and already publishes
    elsewhere on the dashboard.

    This returns a flat list of independent items. It deliberately does not
    rank them, score them, weight them, or combine them into any single
    figure — doing so would manufacture a conclusion the underlying data
    cannot support. A festival window, a fuel-price story and a carrier's
    last disclosed margin are three separate real facts; which (if any)
    explains a given fare is a human judgement, made with these in hand."""
    factors: list[dict] = []

    window = spike_window_for_date(flagged_travel_date)
    if window is not None:
        factors.append(
            {
                "factor_type": "festival_demand_window",
                "window_key": window.key,
                "window_name": window.name,
                "start": window.start.isoformat(),
                "end": window.end.isoformat(),
                "why": window.why,
                "source_note": window.source_note,
            }
        )

    try:
        news = get_airfare_news(gate=gate)
        cutoff = flagged_search_date - dt.timedelta(days=NEWS_LOOKBACK_DAYS)
        for item in news.items:
            if item.published_at is None:
                continue
            published_day = item.published_at.date()
            if cutoff <= published_day <= flagged_search_date:
                factors.append(
                    {
                        "factor_type": "news_item",
                        "title": item.title,
                        "link": item.link,
                        "source": item.source,
                        "published_at": item.published_at.isoformat(),
                        "categories": item.categories,
                        "summary": item.summary,
                    }
                )
    except Exception:
        # News is contextual garnish, not the finding. A news source being
        # unreachable must never take down a flag built from real fare data.
        pass

    financial = financial_context_for_carrier(carrier_code, gate=gate)
    quarters = financial.get("quarters") or []
    factors.append(
        {
            "factor_type": "carrier_financial_context",
            "carrier_code": carrier_code,
            "available": financial["available"],
            "reason": financial["reason"],
            "latest_quarter": quarters[-1] if quarters else None,
        }
    )

    return factors


def persist_anomaly_flags(session: Session, candidates: list[AnomalyCandidate]) -> int:
    """Writes flags, skipping any group-day that already has one (the unique
    constraint on the model). Returns the number of NEW rows written, so a
    re-run reports 0 rather than silently duplicating. An existing flag's
    review status is never overwritten by a re-run."""
    now = dt.datetime.utcnow()
    written = 0
    for c in candidates:
        existing = session.execute(
            select(RegulatorFareFlag).where(
                RegulatorFareFlag.route_id == c.route_id,
                RegulatorFareFlag.carrier_code == c.carrier_code,
                RegulatorFareFlag.ap_window_days == c.ap_window_days,
                RegulatorFareFlag.flagged_search_date
                == dt.datetime.combine(c.flagged_search_date, dt.time.min),
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

        session.add(
            RegulatorFareFlag(
                route_id=c.route_id,
                carrier_code=c.carrier_code,
                ap_window_days=c.ap_window_days,
                flagged_search_date=dt.datetime.combine(c.flagged_search_date, dt.time.min),
                flagged_travel_date=dt.datetime.combine(c.flagged_travel_date, dt.time.min),
                fare_quote_id=c.fare_quote_id,
                observed_fare=c.observed_fare,
                baseline_median_fare=c.baseline_median_fare,
                baseline_mad=c.baseline_mad,
                robust_z_score=c.robust_z_score,
                pct_above_baseline_median=c.pct_above_baseline_median,
                baseline_sample_size=c.baseline_sample_size,
                status="new",
                detected_at=now,
            )
        )
        written += 1

    session.flush()
    return written


def run_anomaly_detection(session: Session, as_of: dt.date | None = None) -> int:
    return persist_anomaly_flags(session, detect_all_anomalies(session, as_of=as_of))
