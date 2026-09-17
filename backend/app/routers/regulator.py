"""Regulator-facing endpoints: real fare-anomaly flags, their review
workflow, draft notice documents, and the public citizen fare-report
intake.

Which endpoints are gated, and why:

  - **Flag listing/detail is public.** A flag is this project's own real
    collected fare plus a stated statistical annotation — the same data the
    public dashboard already shows. Hiding it would be inconsistent with
    everything else here.
  - **Write actions are gated** (reviewing/dismissing a flag, triaging a
    report). An open internet endpoint that lets anyone mark a real flag
    "dismissed" would make the review state meaningless.
  - **Draft notices are gated.** The document is designed to be read as a
    serious evidence packet; leaving it public invites it being lifted out
    of context and passed around as though it were an issued finding,
    which is precisely what its disclaimer exists to prevent.
  - **Citizen report listing is gated, but the count is public.** Reports
    may carry an optional contact email, and they are unverified by
    construction — publishing the raw list would both expose that contact
    detail and risk unverified claims being read with the same weight as
    verified data. The public count keeps the existence and backlog of
    reports honestly visible without either problem.

Nothing here sends anything to any airline or third party. See
app.regulator.notice_draft for why that is a design boundary rather than an
unimplemented feature.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PLAUSIBLE_FARE_INR_RANGE
from app.db.models import Carrier, CitizenFareReport, RegulatorFareFlag
from app.db.session import get_session
from app.index.anomaly_detection import why_context_for_flag
from app.pipeline.clean import is_plausible_fare
from app.regulator.auth import require_regulator_token
from app.regulator.notice_draft import build_draft_notice
from app.schemas import (
    CitizenFareReportIn,
    CitizenFareReportOut,
    CitizenReportCountOut,
    CitizenReportReviewIn,
    DraftNoticeOut,
    RegulatorFlagDetailOut,
    RegulatorFlagOut,
    RegulatorFlagReviewIn,
)

router = APIRouter(prefix="/api/regulator", tags=["regulator"])

# There is deliberately no "sent" status. A flag's lifecycle ends at a human
# decision recorded here; anything issued to an airline happens outside this
# system entirely (see app.regulator.notice_draft).
ALLOWED_REVIEW_STATUSES = {"reviewed", "dismissed"}
ALLOWED_REPORT_STATUSES = {"reviewed"}


def _session():
    with get_session() as session:
        yield session


def _flag_to_out(flag: RegulatorFareFlag, carrier_names: dict[str, str]) -> dict:
    return {
        "id": flag.id,
        "route": flag.route.display_name if flag.route else str(flag.route_id),
        "route_id": flag.route_id,
        "carrier_code": flag.carrier_code,
        "carrier_name": carrier_names.get(flag.carrier_code, flag.carrier_code),
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
    }


def _carrier_names(session: Session) -> dict[str, str]:
    return {c.code: c.name for c in session.execute(select(Carrier)).scalars().all()}


@router.get("/flags", response_model=list[RegulatorFlagOut])
def list_flags(
    status_filter: str | None = None,
    route_id: int | None = None,
    carrier_code: str | None = None,
    session: Session = Depends(_session),
) -> list[RegulatorFlagOut]:
    """Real flagged fares, newest first. `status_filter` accepts
    new|reviewed|dismissed."""
    query = select(RegulatorFareFlag).order_by(
        RegulatorFareFlag.flagged_search_date.desc(), RegulatorFareFlag.id.desc()
    )
    if status_filter:
        query = query.where(RegulatorFareFlag.status == status_filter)
    if route_id is not None:
        query = query.where(RegulatorFareFlag.route_id == route_id)
    if carrier_code:
        query = query.where(RegulatorFareFlag.carrier_code == carrier_code)

    flags = session.execute(query).scalars().all()
    names = _carrier_names(session)
    return [RegulatorFlagOut(**_flag_to_out(f, names)) for f in flags]


@router.get("/flags/{flag_id}", response_model=RegulatorFlagDetailOut)
def get_flag(flag_id: int, session: Session = Depends(_session)) -> RegulatorFlagDetailOut:
    """One flag plus its live `possible_factors` — real, dated context that
    may bear on the fare, never a computed explanation of it."""
    flag = session.get(RegulatorFareFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail=f"no flag with id {flag_id}")

    payload = _flag_to_out(flag, _carrier_names(session))
    payload["possible_factors"] = why_context_for_flag(
        session,
        carrier_code=flag.carrier_code,
        flagged_travel_date=flag.flagged_travel_date.date(),
        flagged_search_date=flag.flagged_search_date.date(),
    )
    return RegulatorFlagDetailOut(**payload)


@router.patch(
    "/flags/{flag_id}/review",
    response_model=RegulatorFlagOut,
    dependencies=[Depends(require_regulator_token)],
)
def review_flag(
    flag_id: int, body: RegulatorFlagReviewIn, session: Session = Depends(_session)
) -> RegulatorFlagOut:
    """Records a human's decision on a flag. `reviewed_by` is a free-text
    label, not a verified identity — see app.regulator.auth."""
    if body.status not in ALLOWED_REVIEW_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(ALLOWED_REVIEW_STATUSES)}",
        )

    flag = session.get(RegulatorFareFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail=f"no flag with id {flag_id}")

    flag.status = body.status
    flag.review_note = body.review_note
    flag.reviewed_by = body.reviewed_by
    flag.reviewed_at = dt.datetime.utcnow()
    session.flush()
    return RegulatorFlagOut(**_flag_to_out(flag, _carrier_names(session)))


@router.get(
    "/flags/{flag_id}/draft-notice",
    response_model=DraftNoticeOut,
    dependencies=[Depends(require_regulator_token)],
)
def flag_draft_notice(flag_id: int, session: Session = Depends(_session)) -> DraftNoticeOut:
    """A DRAFT evidence document for a human regulator to review and, if
    they judge it warranted, act on through their own official channels.
    This endpoint returns a document; it does not send one, and no endpoint
    in this application does."""
    flag = session.get(RegulatorFareFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail=f"no flag with id {flag_id}")
    return DraftNoticeOut(**build_draft_notice(session, flag))


@router.post(
    "/citizen-reports", response_model=CitizenFareReportOut, status_code=status.HTTP_201_CREATED
)
def submit_citizen_report(
    body: CitizenFareReportIn, session: Session = Depends(_session)
) -> CitizenFareReportOut:
    """Open intake for a member of the public. Stored as an explicitly
    unverified report — never merged into the real-data flag table."""
    if not is_plausible_fare(body.reported_fare):
        low, high = PLAUSIBLE_FARE_INR_RANGE
        raise HTTPException(
            status_code=422,
            detail=f"reported_fare must be between INR {low:.0f} and {high:.0f}",
        )
    if not body.origin.strip() or not body.destination.strip():
        raise HTTPException(status_code=422, detail="origin and destination are required")

    report = CitizenFareReport(
        origin=body.origin.strip(),
        destination=body.destination.strip(),
        travel_date=dt.datetime.combine(body.travel_date, dt.time.min),
        reported_fare=body.reported_fare,
        carrier_name=body.carrier_name.strip(),
        note=body.note.strip(),
        contact_email=body.contact_email.strip(),
        submitted_at=dt.datetime.utcnow(),
        status="new",
    )
    session.add(report)
    session.flush()
    return CitizenFareReportOut(
        id=report.id,
        origin=report.origin,
        destination=report.destination,
        travel_date=report.travel_date.date(),
        reported_fare=report.reported_fare,
        carrier_name=report.carrier_name,
        note=report.note,
        contact_email=report.contact_email,
        submitted_at=report.submitted_at,
        status=report.status,
        reviewer_note=report.reviewer_note,
        reviewed_at=report.reviewed_at,
    )


@router.get("/citizen-reports/count", response_model=CitizenReportCountOut)
def citizen_report_count(session: Session = Depends(_session)) -> CitizenReportCountOut:
    """Aggregate counts only — public visibility into how many reports exist
    and how many are still untriaged, without exposing unverified content or
    anyone's contact detail."""
    reports = session.execute(select(CitizenFareReport.status)).all()
    statuses = [r[0] for r in reports]
    return CitizenReportCountOut(
        total=len(statuses),
        new=sum(1 for s in statuses if s == "new"),
        reviewed=sum(1 for s in statuses if s == "reviewed"),
    )


@router.get(
    "/citizen-reports",
    response_model=list[CitizenFareReportOut],
    dependencies=[Depends(require_regulator_token)],
)
def list_citizen_reports(
    status_filter: str | None = None, session: Session = Depends(_session)
) -> list[CitizenFareReportOut]:
    query = select(CitizenFareReport).order_by(CitizenFareReport.submitted_at.desc())
    if status_filter:
        query = query.where(CitizenFareReport.status == status_filter)
    reports = session.execute(query).scalars().all()
    return [
        CitizenFareReportOut(
            id=r.id,
            origin=r.origin,
            destination=r.destination,
            travel_date=r.travel_date.date(),
            reported_fare=r.reported_fare,
            carrier_name=r.carrier_name,
            note=r.note,
            contact_email=r.contact_email,
            submitted_at=r.submitted_at,
            status=r.status,
            reviewer_note=r.reviewer_note,
            reviewed_at=r.reviewed_at,
        )
        for r in reports
    ]


@router.patch(
    "/citizen-reports/{report_id}/review",
    response_model=CitizenFareReportOut,
    dependencies=[Depends(require_regulator_token)],
)
def review_citizen_report(
    report_id: int, body: CitizenReportReviewIn, session: Session = Depends(_session)
) -> CitizenFareReportOut:
    if body.status not in ALLOWED_REPORT_STATUSES:
        raise HTTPException(
            status_code=422, detail=f"status must be one of {sorted(ALLOWED_REPORT_STATUSES)}"
        )

    report = session.get(CitizenFareReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"no citizen report with id {report_id}")

    report.status = body.status
    report.reviewer_note = body.reviewer_note
    report.reviewed_at = dt.datetime.utcnow()
    session.flush()
    return CitizenFareReportOut(
        id=report.id,
        origin=report.origin,
        destination=report.destination,
        travel_date=report.travel_date.date(),
        reported_fare=report.reported_fare,
        carrier_name=report.carrier_name,
        note=report.note,
        contact_email=report.contact_email,
        submitted_at=report.submitted_at,
        status=report.status,
        reviewer_note=report.reviewer_note,
        reviewed_at=report.reviewed_at,
    )
