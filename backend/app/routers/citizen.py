"""What a signed-in traveller gets beyond what everyone already can see.

That list is short by design. The whole analytical surface — index, route
explorer, affordability, festival watch, data sources — stays readable
without an account, because this project's premise is public transparency
about airfares. An account adds exactly two things: the ability to submit a
fare report (see app.routers.regulator for why writing is gated when reading
is not), and this endpoint, which shows what became of the reports you sent.

Gated on being signed in rather than on the traveller role specifically: a
regulator or an airline employee who files a report as a passenger should be
able to follow it, and there is nothing here another role should be denied.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_user, db_session
from app.db.models import CitizenFareReport, User
from app.regulator.views import report_to_out
from app.schemas import CitizenFareReportOut

router = APIRouter(prefix="/api/citizen", tags=["citizen"])


@router.get("/my-reports", response_model=list[CitizenFareReportOut])
def my_reports(
    user: User = Depends(current_user), session: Session = Depends(db_session)
) -> list[CitizenFareReportOut]:
    """Fare reports submitted by the signed-in account, newest first.

    Filtered on the account id from the session, so this can only ever
    return the caller's own reports — there is no parameter that could
    widen it to somebody else's.
    """
    reports = (
        session.execute(
            select(CitizenFareReport)
            .where(CitizenFareReport.submitted_by_user_id == user.id)
            .order_by(CitizenFareReport.submitted_at.desc())
        )
        .scalars()
        .all()
    )
    return [CitizenFareReportOut(**report_to_out(r)) for r in reports]
