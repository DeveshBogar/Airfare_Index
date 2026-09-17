"""Access gate for the regulator-only endpoints.

This is a single shared token, checked against the REGULATOR_ACCESS_TOKEN
environment variable. It is **prototype-grade access control and nothing
more**, and it is important to be precise about what that means:

  - It is NOT authentication. It proves someone holds a shared secret, not
    who they are. Anyone with the token is indistinguishable from anyone
    else with the token.
  - It is NOT an audit trail. RegulatorFareFlag.reviewed_by is free text
    the caller types in; the system cannot verify it.
  - It is NOT authorization. There are no roles, scopes, or per-action
    permissions — the token opens every gated endpoint or none.

What it *is*: enough to stop the write actions (reviewing/dismissing a
flag, triaging a citizen report) and the draft-notice document from being
open to the public internet, which would be indefensible for a tool
positioned at regulators. A real deployment would put a proper identity
provider in front of this; the boundary is documented in
docs/regulator_flagging_methodology.md rather than glossed over.

Failure posture matches app.scraper.compliance.ComplianceGate, which fails
closed when it cannot verify robots.txt: if no token is configured at all,
gated endpoints return 503 rather than falling open. A misconfigured
deployment therefore locks itself, instead of quietly publishing the
regulator surface to everyone.
"""
from __future__ import annotations

import os
import secrets

from fastapi import Header, HTTPException, status

TOKEN_ENV_VAR = "REGULATOR_ACCESS_TOKEN"
TOKEN_HEADER = "X-Regulator-Token"


def configured_token() -> str | None:
    """Read fresh on every call rather than captured at import time — so
    rotating the token doesn't require a restart, and so tests can set it
    per-case. Deliberately never stored in app.config (which is committed)."""
    token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    return token or None


def require_regulator_token(
    x_regulator_token: str | None = Header(default=None, alias=TOKEN_HEADER),
) -> None:
    """FastAPI dependency. Raises 503 when no token is configured (fail
    closed), 401 when one is configured but the request doesn't match."""
    expected = configured_token()
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"regulator endpoints are unavailable: no {TOKEN_ENV_VAR} is configured "
                f"on the server, so access cannot be verified (failing closed)"
            ),
        )

    provided = (x_regulator_token or "").strip()
    # compare_digest rather than == so a wrong token can't be narrowed down
    # by timing how long the comparison took.
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"missing or invalid {TOKEN_HEADER} header",
        )
