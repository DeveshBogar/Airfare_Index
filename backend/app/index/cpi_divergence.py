"""CPI divergence: the problem statement's core thesis made visible — the
official Consumer Price Index only captures airfare movement once a month
(with a ~5-6 week publication lag), while real fares can swing by double
digits within days. This module compares APIx's real, tracked movement
against the last officially published MoSPI CPI figure for the closest
matching category, "Passenger transport services".

This is a same-basket-vs-official comparison, not a claim that our basket
*is* the official statistic — APIx tracks a 20-route basket of domestic
air fares only, while the official group also includes rail and road
passenger fares nationwide. The comparison is honest about that scope
difference (see MOSPI_CPI_REFERENCE.source_note) rather than implying
apples-to-apples equivalence.
"""
from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import MOSPI_CPI_REFERENCE
from app.db.models import IndexValue


def _apix_recent_move(session: Session) -> dict | None:
    rows = session.execute(
        select(IndexValue.date, IndexValue.value)
        .where(IndexValue.frequency == "daily", IndexValue.method == "fisher")
        .order_by(IndexValue.date)
    ).all()
    if len(rows) < 2:
        return None

    first_date, first_value = rows[0]
    last_date, last_value = rows[-1]
    change_pct = 100 * (last_value - first_value) / first_value
    return {
        "first_date": first_date.date(),
        "last_date": last_date.date(),
        "days": (last_date.date() - first_date.date()).days,
        "change_pct": change_pct,
    }


def cpi_divergence(session: Session) -> dict:
    mospi = asdict(MOSPI_CPI_REFERENCE)
    move = _apix_recent_move(session)

    if move is None:
        return {
            "has_signal": False,
            "alert": False,
            "message": (
                "Not enough real APIx history yet to compare against official CPI — "
                "we need at least two real days of index values first."
            ),
            "apix_change_pct": None,
            "apix_days_tracked": None,
            "apix_first_date": None,
            "apix_last_date": None,
            "ratio_vs_official_yoy": None,
            "mospi": mospi,
        }

    apix_pct = move["change_pct"]
    official_pct = MOSPI_CPI_REFERENCE.passenger_transport_yoy_pct
    ratio = abs(apix_pct) / abs(official_pct) if official_pct else None
    alert = ratio is not None and ratio >= 1.0
    days_label = f"{move['days']} day{'s' if move['days'] != 1 else ''}"

    if alert:
        message = (
            f"In just the {days_label} we've tracked so far, APIx has moved {apix_pct:+.1f}% — "
            f"already more than the {official_pct:.2f}% the official Passenger Transport Services CPI "
            f"captured over the ENTIRE year to {MOSPI_CPI_REFERENCE.reference_month_label}."
        )
    else:
        message = (
            f"Over the {days_label} we've tracked so far, APIx has moved {apix_pct:+.1f}%, versus "
            f"{official_pct:.2f}% for the official Passenger Transport Services CPI across the whole "
            f"year to {MOSPI_CPI_REFERENCE.reference_month_label}."
        )

    return {
        "has_signal": True,
        "alert": alert,
        "message": message,
        "apix_change_pct": round(apix_pct, 2),
        "apix_days_tracked": move["days"],
        "apix_first_date": move["first_date"],
        "apix_last_date": move["last_date"],
        "ratio_vs_official_yoy": round(ratio, 1) if ratio is not None else None,
        "mospi": mospi,
    }
