"""Sign-in for the three segregated roles.

One login endpoint serves all three audiences rather than three separate
ones. The role lives on the account, so a per-role endpoint would only let
a caller discover which role a username has by watching which endpoint
accepts it — a worse outcome than the single form the frontend already
shows.

There is no registration endpoint here. Accounts are provisioned with
``python -m app.cli create-user`` (see app/cli.py). For regulator and
operator logins that is the point: the right to review flags, or to answer
on behalf of an airline, is not something a visitor should be able to grant
themselves by filling in a form.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth.deps import current_user, db_session
from app.auth.roles import ROLE_LABELS
from app.auth.service import authenticate
from app.auth.tokens import issue_token
from app.db.models import Carrier, User
from app.schemas import LoginIn, SessionOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(session: Session, user: User) -> UserOut:
    carrier_name = None
    if user.carrier_code:
        carrier = session.get(Carrier, user.carrier_code)
        carrier_name = carrier.name if carrier else user.carrier_code

    return UserOut(
        id=user.id,
        username=user.username,
        role=user.role,
        role_label=ROLE_LABELS.get(user.role, user.role),
        display_name=user.display_name,
        organisation=user.organisation,
        carrier_code=user.carrier_code,
        carrier_name=carrier_name,
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, session: Session = Depends(db_session)) -> SessionOut:
    """Exchange a username and password for a signed session token.

    Every failure — unknown username, wrong password, deactivated account —
    returns the same 401 with the same message, so the response cannot be
    used to enumerate which accounts exist.
    """
    user = authenticate(session, username=body.username, password=body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token, expires_at = issue_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        carrier_code=user.carrier_code,
    )
    return SessionOut(token=token, expires_at=expires_at, user=user_out(session, user))


@router.get("/me", response_model=UserOut)
def me(
    user: User = Depends(current_user), session: Session = Depends(db_session)
) -> UserOut:
    """Who the bearer token belongs to. The frontend calls this on load to
    restore a session, and a 401 here is its signal to show the signed-out
    view."""
    return user_out(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    """Ends the session from the client's point of view only.

    Tokens are stateless and carry their own expiry (see app.auth.tokens),
    so there is nothing server-side to delete — the client discards the
    token and stops sending it. The endpoint exists so the frontend has one
    honest thing to call, and so this limitation is stated somewhere rather
    than implied by the absence of a route.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)
