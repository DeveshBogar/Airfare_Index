"""'Best time to book' advice: turns one route's lead-time elasticity curve
into a plain-language verdict — should a traveller book now or does waiting
tend to pay off on this route.

This is deliberately a *historical pattern*, not a prediction: it compares
real observed mean fares across the advance-purchase windows we've actually
collected for the route, and says so honestly when there isn't enough data
to say anything. No fare is ever synthesised to fill a gap.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.index.elasticity import lead_time_curve

# Below this gap, the difference is within normal day-to-day fare noise —
# calling it a "pattern" would overclaim a signal that isn't really there.
MIN_MEANINGFUL_GAP_PCT = 5.0


def booking_advice(session: Session, route_id: int) -> dict:
    curve = lead_time_curve(session, route_id=route_id)

    if len(curve) < 2:
        return {
            "has_signal": False,
            "verdict": None,
            "message": (
                "Not enough real prices yet for this route to say — we need fares "
                "from at least two different booking windows first."
            ),
            "cheapest_window_days": None,
            "cheapest_mean_fare": None,
            "priciest_window_days": None,
            "priciest_mean_fare": None,
            "gap_pct": None,
            "windows_with_data": len(curve),
            "confidence": None,
        }

    # Which window is cheaper ON AVERAGE, and by how much, is a genuine
    # statistical question about the lead-time effect - window selection
    # and gap_pct (used in the "book early/late" message below) both stay
    # mean-based. But the FARE VALUE reported for that window is its real
    # minimum, not its mean: the mean mixes every SpiceJet fare class with
    # however many carriers/re-scrapes ran, and "cheapest so far" should
    # be a real observed minimum, not an average pulled up by premium
    # fare classes - see cheapest_mean_fare/priciest_mean_fare below.
    cheapest = min(curve, key=lambda p: p["mean_fare"])
    priciest = max(curve, key=lambda p: p["mean_fare"])
    gap_pct = 100 * (priciest["mean_fare"] - cheapest["mean_fare"]) / priciest["mean_fare"]

    total_samples = sum(p["sample_size"] for p in curve)
    if len(curve) >= 4 and total_samples >= 15:
        confidence = "high"
    elif len(curve) >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    if gap_pct < MIN_MEANINGFUL_GAP_PCT:
        verdict = "no_strong_pattern"
        message = (
            f"Prices for this route haven't varied much by how far ahead people booked "
            f"(about {gap_pct:.0f}% difference) — book whenever suits you."
        )
    elif cheapest["ap_window_days"] > priciest["ap_window_days"]:
        verdict = "book_early"
        message = (
            f"Booking {cheapest['ap_window_days']} days ahead has cost about {gap_pct:.0f}% less "
            f"than booking {priciest['ap_window_days']} day(s) ahead on this route — book early if you can."
        )
    else:
        verdict = "can_wait"
        message = (
            f"Booking closer to departure ({cheapest['ap_window_days']} day(s) ahead) has cost about "
            f"{gap_pct:.0f}% less than booking {priciest['ap_window_days']} days ahead on this route — "
            f"no need to rush."
        )

    return {
        "has_signal": True,
        "verdict": verdict,
        "message": message,
        "cheapest_window_days": cheapest["ap_window_days"],
        "cheapest_mean_fare": cheapest["min_fare"],
        "priciest_window_days": priciest["ap_window_days"],
        "priciest_mean_fare": priciest["min_fare"],
        "gap_pct": round(gap_pct, 1),
        "windows_with_data": len(curve),
        "confidence": confidence,
    }
