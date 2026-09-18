"""Shared row-to-payload serialisers for flags and citizen reports.

These live outside the routers because the same two row types are now read
from more than one surface — a flag by both the regulator working the
review queue and the airline answering it, a citizen report by both the
regulator triaging it and the person who submitted it. One serialiser per
row type means a field cannot appear on one surface and silently go
missing from the other.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Carrier, CitizenFareReport, RegulatorFareFlag


def carrier_names(session: Session) -> dict[str, str]:
    return {c.code: c.name for c in session.execute(select(Carrier)).scalars().all()}


def flag_to_out(flag: RegulatorFareFlag, names: dict[str, str]) -> dict:
    return {
        "id": flag.id,
        "route": flag.route.display_name if flag.route else str(flag.route_id),
        "route_id": flag.route_id,
        "carrier_code": flag.carrier_code,
        "carrier_name": names.get(flag.carrier_code, flag.carrier_code),
        "ap_window_days": flag.ap_window_days,
        "flagged_search_date": flag.flagged_search_date.date(),
        "flagged_travel_date": flag.flagged_travel_date.date(),
        "observed_fare": flag.observed_fare,
        "baseline_median_fare": flag.baseline_median_fare,
        "baseline_mad": flag.baseline_mad,
        "robust_z_score": flag.robust_z_score,
        "pct_above_baseline_median": flag.pct_above_baseline_median,
        "baseline_sample_size": flag.baseline_sample_size,
        "status": flag.status,
        "review_note": flag.review_note,
        "reviewed_by": flag.reviewed_by,
        "reviewed_at": flag.reviewed_at,
        "detected_at": flag.detected_at,
        "operator_response": flag.operator_response or "",
        "operator_responded_by": flag.operator_responded_by or "",
        "operator_responded_at": flag.operator_responded_at,
    }


def report_to_out(report: CitizenFareReport) -> dict:
    return {
        "id": report.id,
        "origin": report.origin,
        "destination": report.destination,
        "travel_date": report.travel_date.date(),
        "reported_fare": report.reported_fare,
        "carrier_name": report.carrier_name,
        "note": report.note,
        "contact_email": report.contact_email,
        "submitted_at": report.submitted_at,
        "status": report.status,
        "reviewer_note": report.reviewer_note,
        "reviewed_at": report.reviewed_at,
    }
