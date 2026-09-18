"""FastAPI dependencies that turn a bearer token into a role-checked user.

Two things here are deliberate and easy to get wrong:

  - **The database is authoritative, not the token.** Every request
    re-loads the account and reads the role from that row. The role baked
    into the token is never trusted for an access decision, so changing an
    account's role or deactivating it takes effect on the very next
    request instead of whenever the token happens to expire.
  - **401 and 403 mean different things.** 401 is "you are not signed in",
    403 is "you are signed in, but this is not yours". Collapsing them
    would leave the frontend unable to tell a session that needs renewing
    from a page the user simply may not see.
"""
from __future__ import annotations

from typing import Callable, Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.roles import ROLE_OPERATOR, ROLE_REGULATOR
from app.auth.tokens import TokenError, decode_token
from app.db.models import User
from app.db.session import get_session

UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


def db_session() -> Iterator[Session]:
    with get_session() as session:
        yield session


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(db_session),
) -> User:
    """Require a signed-in user, whatever their role.

    Every failure mode — no header, wrong scheme, bad signature, expired,
    unknown account, deactivated account — raises the same 401, so a probe
    cannot learn from the response which of those it hit.

    There is deliberately no "optional user" variant. Public endpoints here
    are public to everybody and behave identically whether or not a token is
    present, so nothing needs to ask "who is this, if anyone?".
    """
    token = _bearer_token(authorization)
    claims = None
    if token is not None:
        try:
            claims = decode_token(token)
        except TokenError:
            claims = None

    user = session.get(User, claims.user_id) if claims is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="sign in to continue",
            headers=UNAUTHENTICATED_HEADERS,
        )
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Build a dependency admitting only the listed roles."""
    allowed = set(roles)

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"this action requires one of these roles: {sorted(allowed)} — "
                    f"you are signed in as {user.role}"
                ),
            )
        return user

    return dependency


require_regulator = require_role(ROLE_REGULATOR)


def require_operator(user: User = Depends(require_role(ROLE_OPERATOR))) -> User:
    """An operator, guaranteed to carry the carrier code its queries scope to.

    The model-level invariant already makes a carrier-less operator
    unwritable, so this is a belt-and-braces check on the read path: if it
    ever fires, something bypassed the ORM, and returning 500 is far better
    than running an operator query with `carrier_code IS NULL` and quietly
    serving whatever that matches.
    """
    if not user.carrier_code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"operator account {user.username!r} has no carrier binding",
        )
    return user
