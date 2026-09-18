"""Regulator-facing endpoints: real fare-anomaly flags, their review
workflow, draft notice documents, and the public citizen fare-report
intake.

Access is by role (see app.auth.roles). Everything here except the public
fare-report intake and its aggregate count requires a signed-in account
whose role is `regulator`. This replaced a single shared token, and the
difference matters — a shared secret proved only that the caller held it,
so every reviewer was indistinguishable from every other one and
`reviewed_by` could not be more than free text. It now comes from the
session, which makes the review trail an actual record of who decided what.

Which endpoints are gated, and why:

  - **Flags are regulator-only, listing and detail both.** A flag names a
    specific carrier on a specific route and date. However carefully it is
    labelled as a statistical observation, published openly it reads as an
    accusation, and it would be quoted as one. Whether any of it warrants
    action is a human regulator's judgement to make before it goes
    anywhere, so the flag queue does not leave that desk. The one
    exception is the carrier itself, which can see the flags raised against
    it via app.routers.operator — the subject of a review being able to
    read and answer it is due process, not a leak.
  - **Write actions are gated** (reviewing/dismissing a flag, triaging a
    report). An open endpoint letting anyone mark a real flag "dismissed"
    would make the review state meaningless.
  - **Draft notices are gated.** The document is designed to be read as a
    serious evidence packet; leaving it public invites it being lifted out
    of context and passed around as though it were an issued finding,
    which is precisely what its disclaimer exists to prevent.
  - **Submitting a fare report needs any signed-in account; the raw list
    needs a regulator; the aggregate count is public.** Submission is the
    one thing a traveller signs in for, because an unauthenticated write
    endpoint feeding a human triage queue invites being flooded with junk.
    The raw list stays regulator-only: reports may carry an optional
    contact email and are unverified by construction, so publishing them
    would both expose that contact detail and risk unverified claims being
    read with the weight of measured data. The count is public so the
    backlog is honestly visible on the public report page.

Nothing here sends anything to any airline or third party. See
app.regulator.notice_draft for why that is a design boundary rather than an
unimplemented feature.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_user, db_session, require_regulator
from app.config import PLAUSIBLE_FARE_INR_RANGE
from app.db.models import CitizenFareReport, RegulatorFareFlag, User
from app.index.anomaly_detection import why_context_for_flag
from app.pipeline.clean import is_plausible_fare
from app.regulator.notice_draft import build_draft_notice
from app.regulator.views import carrier_names, flag_to_out, report_to_out
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


@router.get(
    "/flags",
    response_model=list[RegulatorFlagOut],
    dependencies=[Depends(require_regulator)],
)
def list_flags(
    status_filter: str | None = None,
    route_id: int | None = None,
    carrier_code: str | None = None,
    session: Session = Depends(db_session),
) -> list[RegulatorFlagOut]:
    """Real flagged fares, newest first. `status_filter` accepts
    new|reviewed|dismissed. Regulator-only — see this module's docstring."""
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
    names = carrier_names(session)
    return [RegulatorFlagOut(**flag_to_out(f, names)) for f in flags]


@router.get(
    "/flags/{flag_id}",
    response_model=RegulatorFlagDetailOut,
    dependencies=[Depends(require_regulator)],
)
def get_flag(flag_id: int, session: Session = Depends(db_session)) -> RegulatorFlagDetailOut:
    """One flag plus its live `possible_factors` — real, dated context that
    may bear on the fare, never a computed explanation of it."""
    flag = session.get(RegulatorFareFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail=f"no flag with id {flag_id}")

    payload = flag_to_out(flag, carrier_names(session))
    payload["possible_factors"] = why_context_for_flag(
        session,
        carrier_code=flag.carrier_code,
        flagged_travel_date=flag.flagged_travel_date.date(),
        flagged_search_date=flag.flagged_search_date.date(),
    )
    return RegulatorFlagDetailOut(**payload)


@router.patch("/flags/{flag_id}/review", response_model=RegulatorFlagOut)
def review_flag(
    flag_id: int,
    body: RegulatorFlagReviewIn,
    reviewer: User = Depends(require_regulator),
    session: Session = Depends(db_session),
) -> RegulatorFlagOut:
    """Records a regulator's decision on a flag.

    `reviewed_by` is taken from the signed-in account, never from the
    request body — a caller must not be able to attribute a review decision
    to somebody else.
    """
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
    flag.reviewed_by = reviewer.username
    flag.reviewed_at = dt.datetime.utcnow()
    session.flush()
    return RegulatorFlagOut(**flag_to_out(flag, carrier_names(session)))


@router.get(
    "/flags/{flag_id}/draft-notice",
    response_model=DraftNoticeOut,
    dependencies=[Depends(require_regulator)],
)
def flag_draft_notice(flag_id: int, session: Session = Depends(db_session)) -> DraftNoticeOut:
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
    body: CitizenFareReportIn,
    submitter: User = Depends(current_user),
    session: Session = Depends(db_session),
) -> CitizenFareReportOut:
    """Intake for a member of the public. Stored as an explicitly unverified
    report — never merged into the real-data flag table.

    Requires an account, unlike everything else a traveller does here.
    Reading is open to anyone; writing is not, because an unauthenticated
    write endpoint feeding a human triage queue is an open invitation to
    flood it. Attaching each report to an account makes a spammer
    identifiable and their reports removable as a set.

    Any signed-in role may file one: a regulator or an airline employee who
    books a flight is also a traveller, and inventing a rule that they
    cannot report a fare would add a failure mode without protecting
    anything.
    """
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
        submitted_by_user_id=submitter.id,
    )
    session.add(report)
    session.flush()
    return CitizenFareReportOut(**report_to_out(report))


@router.get("/citizen-reports/count", response_model=CitizenReportCountOut)
def citizen_report_count(session: Session = Depends(db_session)) -> CitizenReportCountOut:
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
    dependencies=[Depends(require_regulator)],
)
def list_citizen_reports(
    status_filter: str | None = None, session: Session = Depends(db_session)
) -> list[CitizenFareReportOut]:
    query = select(CitizenFareReport).order_by(CitizenFareReport.submitted_at.desc())
    if status_filter:
        query = query.where(CitizenFareReport.status == status_filter)
    reports = session.execute(query).scalars().all()
    return [CitizenFareReportOut(**report_to_out(r)) for r in reports]


@router.patch(
    "/citizen-reports/{report_id}/review",
    response_model=CitizenFareReportOut,
    dependencies=[Depends(require_regulator)],
)
def review_citizen_report(
    report_id: int, body: CitizenReportReviewIn, session: Session = Depends(db_session)
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
    return CitizenFareReportOut(**report_to_out(report))
