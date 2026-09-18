"""Account creation and credential checking.

Kept separate from the FastAPI dependencies in app.auth.deps so that the
CLI seeding path and the HTTP login path go through exactly the same
validation — a role/carrier rule that only held for one of them would be
worse than none at all.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.auth.roles import ROLE_OPERATOR, validate_role_carrier_pairing
from app.db.models import Carrier, User

# Verified against a throwaway hash when the username does not exist, so a
# failed login costs the same wall-clock time either way. Without it, a
# prober can tell "no such user" (fast) from "wrong password" (one scrypt
# derivation slower) and enumerate valid usernames.
_TIMING_DECOY_HASH = hash_password("timing-decoy-never-a-real-password")


class AccountError(Exception):
    """Raised for a bad account request — duplicate username, unknown
    carrier, or a role/carrier pairing that does not make sense."""


def normalise_username(username: str) -> str:
    """Usernames are matched case-insensitively and stored lowercase.

    Two accounts differing only in case would be indistinguishable in an
    audit trail, which is the one thing this table exists to make possible.
    """
    return username.strip().lower()


def create_user(
    session: Session,
    *,
    username: str,
    password: str,
    role: str,
    carrier_code: str | None = None,
    display_name: str = "",
    organisation: str = "",
) -> User:
    """Create one account, validating the role/carrier pairing first."""
    name = normalise_username(username)
    if not name:
        raise AccountError("username is required")

    carrier = (carrier_code or "").strip().upper() or None
    try:
        validate_role_carrier_pairing(role, carrier)
    except ValueError as exc:
        raise AccountError(str(exc)) from exc

    existing = session.execute(
        select(User).where(func.lower(User.username) == name)
    ).scalar_one_or_none()
    if existing is not None:
        raise AccountError(f"username {name!r} is already taken")

    if role == ROLE_OPERATOR:
        # An operator bound to a carrier that does not exist would pass the
        # pairing check and then match nothing at query time, which reads as
        # a broken permission filter rather than a bad account.
        if session.get(Carrier, carrier) is None:
            known = [c.code for c in session.execute(select(Carrier)).scalars().all()]
            raise AccountError(f"unknown carrier {carrier!r} — known carriers: {known}")

    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        raise AccountError(str(exc)) from exc

    user = User(
        username=name,
        password_hash=password_hash,
        role=role,
        carrier_code=carrier,
        display_name=display_name.strip(),
        organisation=organisation.strip(),
        is_active=True,
        created_at=dt.datetime.utcnow(),
    )
    session.add(user)
    session.flush()
    return user


def set_password(user: User, password: str) -> None:
    try:
        user.password_hash = hash_password(password)
    except ValueError as exc:
        raise AccountError(str(exc)) from exc


def authenticate(session: Session, *, username: str, password: str) -> User | None:
    """Return the matching active user, or None.

    One None for every failure — unknown user, wrong password, deactivated
    account — so the caller returns a single 401 and the response cannot be
    used to work out which accounts exist.
    """
    name = normalise_username(username)
    user = session.execute(
        select(User).where(func.lower(User.username) == name)
    ).scalar_one_or_none()

    if user is None:
        verify_password(password, _TIMING_DECOY_HASH)
        return None

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_active:
        return None

    user.last_login_at = dt.datetime.utcnow()
    session.flush()
    return user
